import argparse
import random
import numpy as np
import torch
from transformers.file_utils import is_torch_available
from datasets import load_dataset, load_metric, concatenate_datasets
from transformers import AutoTokenizer, AutoModelForSequenceClassification, TrainingArguments, Trainer
from sklearn.metrics import f1_score, precision_recall_curve, auc

import os
import sys

currDir = os.path.dirname(os.path.realpath(__file__))
rootDir = os.path.abspath(os.path.join(currDir, '..'))
if rootDir not in sys.path:  # add parent dir to paths
    sys.path.append(rootDir)

parser = argparse.ArgumentParser(description='set model, optimizer and if you want to tune all hyperparams or only lr')

parser.add_argument("-o", "--optim", type=str, choices=['adamw', 'adam', 'adamax', 'sgd', 'sgdm'],
                    default='adam', help="choose optimizer")

parser.add_argument("-m", "--model", type=str, choices=['roberta', 'bert'],
                    default='bert', help="choose transformer model")

parser.add_argument("-s", "--seed", type=int, choices=[1, 10, 100, 1000, 10000],
                    default=1, help="choose seed")

args = parser.parse_args()

if args.model == 'bert':
    model_checkpoint = 'distilbert-base-uncased'
else:
    model_checkpoint = 'distilroberta-base'
optim = args.optim

s = args.seed

task = "cola"

# Custom seed
def set_seed(seed: int):
    """
    Helper function for reproducible behavior to set the seed in ``random``, ``numpy``, ``torch`` and/or ``tf`` (if
    installed).

    Args:
        seed (:obj:`int`): The seed to set.
    """
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


set_seed(1)

tokenizer = AutoTokenizer.from_pretrained(model_checkpoint, use_fast=True)
GLUE_TASKS = ["cola", "mnli", "mnli-mm", "mrpc", "qnli", "qqp", "rte", "sst2", "stsb", "wnli"]
task_to_keys = {
    "cola": ("sentence", None),
    "mnli": ("premise", "hypothesis"),
    "mnli-mm": ("premise", "hypothesis"),
    "mrpc": ("sentence1", "sentence2"),
    "qnli": ("question", "sentence"),
    "qqp": ("question1", "question2"),
    "rte": ("sentence1", "sentence2"),
    "sst2": ("sentence", None),
    "stsb": ("sentence1", "sentence2"),
    "wnli": ("sentence1", "sentence2"),
}

sentence1_key, sentence2_key = task_to_keys[task]

def preprocess_function(examples):
    if sentence2_key is None:
        return tokenizer(examples[sentence1_key], truncation=True)
    return tokenizer(examples[sentence1_key], examples[sentence2_key], truncation=True)

num_labels = 3 if task.startswith("mnli") else 1 if task == "stsb" else 2

def model_init():
    model = AutoModelForSequenceClassification.from_pretrained(model_checkpoint, num_labels=num_labels)
    return model

def compute_metrics(eval_pred):
    predictions, labels = eval_pred
    predictions = np.argmax(predictions, axis=1)
    matthews = metric.compute(predictions=predictions, references=labels)['matthews_correlation']

    f1_pos = f1_score(y_true=labels, y_pred=predictions, pos_label=1)
    f1_neg = f1_score(y_true=labels, y_pred=predictions, pos_label=0)
    f1_macro = f1_score(y_true=labels, y_pred=predictions, average='macro')
    f1_micro = f1_score(y_true=labels, y_pred=predictions, average='micro')

    return {
        'matthews_correlation': matthews,
        'f1_positive': f1_pos,
        'f1_negative': f1_neg,
        'macro_f1': f1_macro,
        'micro_f1': f1_micro
    }

# Loading the dataset
actual_task = "mnli" if task == "mnli-mm" else task
dataset = load_dataset("glue", actual_task)
metric = load_metric('glue', actual_task)

dataset1 = concatenate_datasets([dataset["train"], dataset["validation"]])

dataset2 = dataset1.train_test_split(test_size=0.1666666666666, seed=s, stratify_by_column='label')

train = dataset2["train"]
valid = dataset2["test"].train_test_split(test_size=0.5, seed=s, stratify_by_column='label')["train"]
test = dataset2["test"].train_test_split(test_size=0.5, seed=s, stratify_by_column='label')["test"]

encoded_train = train.map(preprocess_function, batched=True)
encoded_valid = valid.map(preprocess_function, batched=True)
encoded_test = test.map(preprocess_function, batched=True)

# AUC
# Precision-Recall-F1s
# class 1 is positive
def prec_rec_f1(y, predictions,
                c=1):  # returns matrix(2,3) where the 1st row prf1 of given class, the 2nd row macro-rpf1
    TP = 0
    FP = 0
    FN = 0
    TN = 0

    for i in range(len(y)):
        if y[i] == 1 and predictions[i] == 1:
            TP += 1
        elif y[i] == 0 and predictions[i] == 1:
            FP += 1
        elif y[i] == 1 and predictions[i] == 0:
            FN += 1
        elif y[i] == 0 and predictions[i] == 0:
            TN += 1

    if FP == 0:
        precision_positive = 1
    else:
        precision_positive = TP / (TP + FP)
    if FN == 0:
        recall_positive = 1
    else:
        recall_positive = TP / (TP + FN)
    f1_positive = (2 * precision_positive * recall_positive) / (precision_positive + recall_positive)

    if FN == 0:
        precision_negative = 1
    else:
        precision_negative = TN / (TN + FN)
    if FP == 0:
        recall_negative = 1
    else:
        recall_negative = TN / (TN + FP)
    f1_negative = (2 * precision_negative * recall_negative) / (precision_negative + recall_negative)

    if c == 1:
        return precision_positive, recall_positive, f1_positive

    elif c == 0:
        return precision_negative, recall_negative, f1_negative

# Scores printing
def scores(y, pred, prob_pos, prob_neg):
    p_pos, rec_pos, f1_pos = prec_rec_f1(y, pred, c=1)
    p_neg, rec_neg, f1_neg = prec_rec_f1(y, pred, c=0)

    # AUC
    precision, recall, thresholds = precision_recall_curve(y, prob_pos, pos_label=1)
    pos_prec = precision
    pos_recall = recall
    auc_pos = auc(recall, precision)

    precision, recall, thresholds = precision_recall_curve(y, prob_neg, pos_label=0)
    neg_prec = precision
    neg_recall = recall
    auc_neg = auc(recall, precision)

    macro_precision = (p_neg + p_pos) / 2
    macro_recall = (rec_neg + rec_pos) / 2
    macro_f1 = (2 * macro_precision * macro_recall) / (macro_precision + macro_recall)
    macro_auc = (auc_pos + auc_neg) / 2

    f.write("Negative class f1-score: {:.2f}%".format(f1_neg * 100)+ '\n')
    f.write("Positive class f1-score: {:.2f}%".format(f1_pos * 100)+ '\n')
    f.write("precision-recall AUC score negative class: {:.2f}%".format(auc_neg * 100)+ '\n')
    f.write("precision-recall AUC score positive class: {:.2f}%".format(auc_pos * 100)+ '\n')

    f.write("--- MACRO-AVERAGED RESULTS ---\n")
    f.write("macro-f1-score: {:.2f}%".format(macro_f1 * 100)+ '\n')
    f.write("macro-precision-recall AUC score: {:.2f}%\n------------------------------\n".format(macro_auc * 100)+ '\n')

    return pos_prec, pos_recall, neg_prec, neg_recall


from scipy.special import softmax



def eval_and_predict(data, y):
    predictions, labels, _ = trainer.predict(data)
    probs = softmax(predictions)
    preds = softmax(predictions).argmax(-1)
    return scores(y, preds, probs[:, 1], probs[:, 0])


from optimizers.Adam import MyTrainingArguments, MyTrainer

training_args = MyTrainingArguments(
        do_eval=True,
        eval_steps=500,
        optim=optim,
        per_device_train_batch_size=4,
        per_device_eval_batch_size=4,
        evaluation_strategy="steps",
        logging_steps=500,
        save_total_limit=2,
        warmup_steps=500,
        num_train_epochs=10,
        load_best_model_at_end=True,
        logging_dir="1",
        disable_tqdm=False,
        output_dir="./out"
    )

trainer = MyTrainer(
    args=training_args,
    tokenizer=tokenizer,
    train_dataset=encoded_train,
    eval_dataset=encoded_valid,
    model_init=model_init,
    compute_metrics=compute_metrics
)

trainer.train()

# f = open(task + '_' + args.model + '_' + args.optim + '_seed_' + str(s) + '.txt', 'w')

# f.write('TRAIN:' + '\n')
# trainer.evaluate(encoded_train, metric_key_prefix="eval")
# f.write('\n')

# f.write('VALID:' + '\n')
# trainer.evaluate(encoded_valid, metric_key_prefix="eval")
# f.write('\n')

# f.write('TEST:' + '\n')
# trainer.evaluate(encoded_test, metric_key_prefix="eval")

# f.write('\n')
# f.close()

f = open(task+'_'+args.model+'_'+ args.optim+'_seed_'+ str(s)+'.txt', 'w')

f.write('TRAIN:' + '\n')
pos_prec, pos_recall, neg_prec, neg_recall = eval_and_predict(encoded_train, train['label'])
f.write('Matthews: ' +str(trainer.evaluate(encoded_train).get('eval_matthews_correlation'))+ '\n')
f.write('f1 pos: '  +str(trainer.evaluate(encoded_train).get('eval_f1_positive') * 100)+ '\n')
f.write('f1 neg: ' +str(trainer.evaluate(encoded_train).get('eval_f1_negative') * 100)+ '\n')
f.write('f1 macro: ' +str(trainer.evaluate(encoded_train).get('eval_macro_f1') * 100)+ '\n')
f.write('\n')
f.write('VALID:' + '\n')
pos_prec, pos_recall, neg_prec, neg_recall = eval_and_predict(encoded_valid, valid['label'])
f.write('Matthews: ' +str(trainer.evaluate(encoded_valid).get('eval_matthews_correlation'))+ '\n')
f.write('f1 pos: ' +str(trainer.evaluate(encoded_valid).get('eval_f1_positive') * 100)+ '\n')
f.write('f1 neg: ' +str(trainer.evaluate(encoded_valid).get('eval_f1_negative') * 100)+ '\n')
f.write('f1 macro: ' +str(trainer.evaluate(encoded_valid).get('eval_macro_f1') * 100)+ '\n')
f.write('\n')
f.write('TEST:' + '\n')
pos_prec, pos_recall, neg_prec, neg_recall = eval_and_predict(encoded_test, test['label'])
f.write('Matthews: ' +str(trainer.evaluate(encoded_test).get('eval_matthews_correlation'))+ '\n')
f.write('f1 pos: ' +str(trainer.evaluate(encoded_test).get('eval_f1_positive') * 100)+ '\n')
f.write('f1 neg: ' +str(trainer.evaluate(encoded_test).get('eval_f1_negative') * 100)+ '\n')
f.write('f1 macro: ' +str(trainer.evaluate(encoded_test).get('eval_macro_f1') * 100)+ '\n')

f.write('\n')


f.close()
