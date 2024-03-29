from utils.utils import load_config
from data_factory.preprocessing import *

import numpy as np
import pandas as pd
import math

import logging
from logging import DEBUG, INFO, WARNING
import pickle
import os

logging.basicConfig(level=DEBUG)
logger = logging.getLogger(__name__)
logger.setLevel(DEBUG)


class DataLoader:
    def __init__(self, config_file='../config/config.yml', train_val_split=0.95, log_level: int = INFO, use_previous_files=True):
        logger.setLevel(log_level)

        config = load_config(config_file)
        # Create variables from config
        self.data_folder = config['data']['path']
        self.train_file = self.data_folder + config['data']['train_file']
        self.test_file = self.data_folder + config['data']['test_file']
        self._do_fill_missing_dates = config['preprocessing']['fill_missing_dates']
        self._do_scale = config['preprocessing']['scale']
        # self._force_positive = config['preprocessing']['positive']
        self._group_to_one_hot = config['preprocessing']['group_to_one_hot']
        self._train_val_split = train_val_split

        self.export_file_name = f"{self.data_folder}/data_export_{config['data']['train_file']}_{config['data']['test_file']}_fmd-{'_'.join([str(i) for i in config['preprocessing'].values()])}.p"

        logger.debug(f'Use config {config}')

        # Load data
        if use_previous_files and os.path.exists(self.export_file_name):
            logger.info(
                f'Use previously generated file {self.export_file_name}. Can not redo preprocessing by loading from generated file.')
            self.from_file()
        else:
            self.load()
            self.preprocess(train_val_split=train_val_split)
            self.to_file()

    def load(self):
        """
        Load data from origin files
        """
        self._df_train = pd.read_csv(self.train_file).rename(columns={'KPI ID': 'kpi_id'})
        logger.info(f'{self.train_file} loaded. shape {self._df_train.shape}')

        self._df_test = pd.read_csv(self.test_file).rename(columns={'KPI ID': 'kpi_id'})
        logger.info(f'{self.test_file} loaded. shape {self._df_test.shape}')

        self._df_train['datetime'] = pd.to_datetime(self._df_train.timestamp, unit='s')
        self._df_test['datetime'] = pd.to_datetime(self._df_test.timestamp, unit='s')

    def preprocess(self, train_val_split):
        if self._do_fill_missing_dates:
            self.__fill_missing_dates()

        self._train, self._val = split_train_val_timeseries(self._df_train, id='kpi_id', train_val_split=train_val_split)
        self._test = self._df_test.copy()
        logger.debug(f'Data split. train: {self._train.shape}  val: {self._val.shape}')

        if self._do_scale:
            self.__scale()

        self._train.sort_values(['kpi_id', 'datetime'], inplace=True)
        self._test.sort_values(['kpi_id', 'datetime'], inplace=True)
        self._val.sort_values(['kpi_id', 'datetime'], inplace=True)

        self._train.reset_index(drop=True, inplace=True)
        self._val.reset_index(drop=True, inplace=True)
        self._test.reset_index(drop=True, inplace=True)

        if self._group_to_one_hot:
            self._train = pd.merge(self._train.reset_index(drop=False),
                                   pd.get_dummies(self._train.kpi_id, prefix='index').reset_index(drop=False),
                                   how='left',
                                   left_on='index', right_on='index')
            self._test = pd.merge(self._test.reset_index(drop=False),
                                  pd.get_dummies(self._test.kpi_id, prefix='index').reset_index(drop=False), how='left',
                                  left_on='index', right_on='index')
            self._val = pd.merge(self._val.reset_index(drop=False),
                                 pd.get_dummies(self._val.kpi_id, prefix='index').reset_index(drop=False), how='left',
                                 left_on='index', right_on='index')
            logger.debug('One hot encoding done.')

        logger.info('Preprocessing done.')

    def __scale(self):
        scalers = train_scalers_on_timeseries(self._train)
        self._train = scale_timeseries(self._train, scalers)
        self._val = scale_timeseries(self._val, scalers)
        self._test = scale_timeseries(self._test, scalers)

        logger.debug('Data scaled')

    def __fill_missing_dates(self):
        self._df_train = fill_missing_dates(
            self._df_train,
            date_col="datetime",
            timestamp_col="timestamp",
            grp_col="kpi_id",
            fill_with_value={"label": 0},
        )
        self._df_test = fill_missing_dates(
            self._df_test,
            date_col="datetime",
            timestamp_col="timestamp",
            grp_col="kpi_id",
        )

        # self._df_train.authentic = self._df_train.authentic.astype(str)
        # self._df_test.authentic = self._df_test.authentic.astype(str)

        self._df_train["timestamp_1"] = (self._df_train.timestamp / 60).astype(int)
        self._df_test["timestamp_1"] = (self._df_test.timestamp / 60).astype(int)

        logger.debug("Fill missing dates done")

    def __dict__(self):
        return {
            'train': self._train,
            'val': self._val,
            'test': self._test
        }

    def to_file(self):
        """
        Export preprocessed data to a file whose name is the config.
        """
        pickle.dump(self.__dict__(), open(self.export_file_name, "wb"))
        logger.info(f'Data exported to "{self.export_file_name}"')

    def from_file(self):
        """
        Load data from previously generated file
        This method of loading does not allow to redo the preprocessing part.
        """
        dt = pickle.load(open(self.export_file_name, "rb"))
        self._train = dt['train']
        self._test = dt['test']
        self._val = dt['val']

    @property
    def train(self):
        return self._train

    @property
    def test(self):
        return self._test

    @property
    def val(self):
        return self._val


if __name__ == '__main__':
    dl = DataLoader(log_level=DEBUG, use_previous_files=False)
    print(dl.train.shape)
    print(dl.val.shape)
    print(dl.test.shape)
