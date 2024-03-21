import datasets
from pytorch_lightning import LightningDataModule
from torch.utils.data import DataLoader
from transformers import AutoTokenizer, DataCollatorWithPadding

import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

class DataModule(LightningDataModule):
    task_text_field_map = {
        "cola": ["sentence"],
        "sst2": ["sentence"],
        "mrpc": ["sentence1", "sentence2"],
        "qqp": ["question1", "question2"],
        "stsb": ["sentence1", "sentence2"],
        "mnli": ["premise", "hypothesis"],
        "qnli": ["question", "sentence"],
        "rte": ["sentence1", "sentence2"],
        "wnli": ["sentence1", "sentence2"],
        "ax": ["premise", "hypothesis"],
    }

    glue_task_num_labels = {
        "cola": 2,
        "sst2": 2,
        "mrpc": 2,
        "qqp": 2,
        "stsb": 1,
        "mnli": 3,
        "qnli": 2,
        "rte": 2,
        "wnli": 2,
        "ax": 3,
    }

    loader_columns = [
        "datasets_idx",
        "input_ids",
        "token_type_ids",
        "attention_mask",
        "start_positions",
        "end_positions",
        "labels",
    ]

    def __init__(
        self,
        model_name_or_path: str,
        task_name: str = "mrpc",
        # max_seq_length: int = 128,
        train_batch_size: int = 32,
        eval_batch_size: int = 32,
        num_workers: int = 4,
        **kwargs,
    ):
        super().__init__()
        self.model_name_or_path = model_name_or_path
        self.task_name = task_name
        # self.max_seq_length = max_seq_length
        self.train_batch_size = train_batch_size
        self.eval_batch_size = eval_batch_size
        self.num_workers = num_workers

        self.text_fields = self.task_text_field_map[task_name]
        self.num_labels = self.glue_task_num_labels[task_name]
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name_or_path, use_fast=True)
        self.data_collator = DataCollatorWithPadding(tokenizer=self.tokenizer)

        # Determine average parameter based on the number of labels
        if self.num_labels == 2:
            self.average = "binary"
        else:
            self.average = "macro"  # Change this to "micro", "macro", "weighted", or None as needed

    def setup(self, stage: str):
        self.dataset = datasets.load_dataset("glue", self.task_name, trust_remote_code=True)

        for split in self.dataset.keys():
            self.dataset[split] = self.dataset[split].map(
                self.convert_to_features,
                batched=True,  
                remove_columns=["label"],
            )
            self.columns = [c for c in self.dataset[split].column_names if c in self.loader_columns]
            self.dataset[split].set_format(type="torch", columns=self.columns)

        self.eval_splits = [x for x in self.dataset.keys() if "validation" in x]

    def prepare_data(self):
        datasets.load_dataset("glue", self.task_name, trust_remote_code=True)
        AutoTokenizer.from_pretrained(self.model_name_or_path)

    def train_dataloader(self):
        return DataLoader(self.dataset["train"], 
                            batch_size=self.train_batch_size, 
                            shuffle=True,
                            num_workers=self.num_workers,
                            collate_fn=self.data_collator,  # Dynamic padding
                            persistent_workers=True
                            )

    def val_dataloader(self):
        if len(self.eval_splits) == 1:
            return DataLoader(self.dataset["validation"], 
                                batch_size=self.eval_batch_size,
                                num_workers=self.num_workers,
                                collate_fn=self.data_collator,  # Dynamic padding
                                persistent_workers=True)
        elif len(self.eval_splits) > 1:
            return [DataLoader(self.dataset[x], 
                                batch_size=self.eval_batch_size,  
                                num_workers=self.num_workers,
                                collate_fn=self.data_collator , # Dynamic padding
                                persistent_workers=True)
                            for x in self.eval_splits
                            ]

    def test_dataloader(self):
        if len(self.eval_splits) == 1:
            return DataLoader(self.dataset["test"], 
                              batch_size=self.eval_batch_size,
                              num_workers=self.num_workers,
                              collate_fn=self.data_collator, # Dynamic padding
                              persistent_workers=True)
        elif len(self.eval_splits) > 1:
            return [DataLoader(self.dataset[x], 
                                batch_size=self.eval_batch_size,
                                num_workers=self.num_workers,
                                collate_fn=self.data_collator,  # Dynamic padding
                                persistent_workers=True)
                            for x in self.eval_splits
                            ]

    def convert_to_features(self, example_batch, indices=None):
        # Either encode single sentence or sentence pairs
        if len(self.text_fields) > 1:
            texts_or_text_pairs = list(zip(example_batch[self.text_fields[0]], example_batch[self.text_fields[1]]))
        else:
            texts_or_text_pairs = example_batch[self.text_fields[0]]

        # Tokenize the text/text pairs
        features = self.tokenizer.batch_encode_plus(
            texts_or_text_pairs, 
            # max_length=self.max_seq_length, 
            pad_to_max_length=False,  # Padding will be done dynamically in DataLoader
            truncation=True
        )

        # Rename label to labels to make it easier to pass to model forward
        features["labels"] = example_batch["label"]

        return features