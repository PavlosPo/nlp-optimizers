from datasets import load_dataset, concatenate_datasets
from transformers import AutoTokenizer, DataCollatorWithPadding
import torch
import evaluate

class CustomDataLoader:
    def __init__(self, dataset_from='glue', model_name = 'bert-based-uncased' ,dataset_task='sst2', seed_num=42, range_to_select=500, batch_size=8):
        self.dataset_from = dataset_from
        self.model_name = model_name
        self.dataset_task = dataset_task
        self.seed_num = seed_num
        self.range_to_select = range_to_select
        self.batch_size = batch_size

        self.GLUE_TASKS = ["cola", "mnli", "mnli-mm", "mrpc", "qnli", "qqp", "rte", "sst2", "stsb", "wnli"]
        self.task_to_keys = {
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
        self.sentence1_key, self.sentence2_key = self.task_to_keys[self.dataset_task]

        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.data_collator = DataCollatorWithPadding(tokenizer=self.tokenizer, padding=True)
        self.metric = evaluate.load(self.dataset_from, self.dataset_task)


    def get_custom_data_loaders(self):
        dataset = load_dataset(self.dataset_from, self.dataset_task).map(self._prepare_dataset, batched=True)
        dataset = concatenate_datasets([dataset["train"], dataset["validation"]]).train_test_split(test_size=0.1666666666666, seed=self.seed_num, stratify_by_column='label')
        

        # TODO: If RANGE_TO_SELECT is defined, select a range of data
        train_dataset = dataset['train'].select(range(self.range_to_select)).remove_columns(['sentence', 'idx']).rename_column('label', 'labels')
        test_dataset = dataset['test'].select(range(self.range_to_select)).remove_columns(['sentence', 'idx']).rename_column('label', 'labels')

        # Define data loaders
        train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=self.batch_size, shuffle=True, collate_fn=self.data_collator)
        test_loader = torch.utils.data.DataLoader(test_dataset, batch_size=self.batch_size, shuffle=True, collate_fn=self.data_collator)
        return train_loader, test_loader, self.metric

    def _prepare_dataset(self, examples):
        """
        Prepare dataset for training and testing. This function will tokenize the examples using the tokenizer provided.
        """
        if self.sentence2_key is None:
            return self.tokenizer(examples[self.sentence1_key], truncation=True)
        return self.tokenizer(examples[self.sentence1_key], examples[self.sentence2_key], truncation=True)