# Copyright 2015 Carnegie Mellon University
#
# Author: Han Chen <hanc@andrew.cmu.edu>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import ast
import falcon
import mock
from monasca.common import kafka_conn
from oslo.config import fixture as fixture_config
from oslotest import base
from monasca.microservice import ks_anomaly_processor

import json

class TestParamUtil(base.BaseTestCase):

    def setUp(self):
        super(TestParamUtil, self).setUp()
        self.req = mock.Mock()

class TestKsAnomalyProcessor(base.BaseTestCase):

    def setUp(self):
        self.CONF = self.useFixture(fixture_config.Config()).conf
        self.CONF.ksanomalyprocess.topic = 'metrics'
        self.CONF.ksanomalyprocess.reference_duration = 3600
        self.CONF.ksanomalyprocess.probe_duration = 600
        self.CONF.ksanomalyprocess.ks_d = 0.5
        self.CONF.ksanomalyprocess.min_samples = 15
        self.CONF.ksanomalyprocess.metric_name_suffix = '.anomaly_score'
        self.CONF.ksanomalyprocess.names = 'cpu.user_perc'
        self.kap = ks_anomaly_processor.KsAnomalyProcessor()
        super(TestKsAnomalyProcessor, self).setUp()

    def test_initialization(self):
        # test that the doc type of the es connection is fake
        self.assertEqual(self.kap._reference_duration, 3600)
        self.assertEqual(self.kap._probe_duration, 600)
        self.assertEqual(self.kap._ks_d, 0.5)
        self.assertEqual(self.kap._min_samples, 15)
        self.assertEqual(self.kap._metric_name_suffix, '.anomaly_score')
        self.assertEqual(self.kap._metric_names, 'cpu.user_perc')

    def test_handle_prediction(self):
        with mock.patch.object(ks_anomaly_processor.KsAnomalyProcessor,
                               '_send_predictions',
                               return_value=""):
            msg = ast.literal_eval(
                '{"name": "cpu.user_perc", '
                '"dimensions": {'
                '"k0": "v0",'
                '"hostname": "Ibmserver"}'
                '"timestamp", 1405630174123,'
                '"value": 20,'
                '"dimensions_hash": "ef3fb07027653934898bc9e3b908c29b"}')

            self.kap.handle_notification_msg(msg)

    def test__send_predictions(self):
        with mock.patch.object(kafka_conn.KafkaConnection,
                               'send_messages',
                               return_value=200):
            with mock.patch.object(ks_anomaly_processor.KsAnomalyProcessor,
                                   '_ks_test',
                                   return_value=""):
                with mock.patch.object(ks_anomaly_processor.KsAnomalyProcessor,
                                       '_ks_test',
                                       return_value=0):
                    metric_id = 'ef3fb07027653934898bc9e3b908c29b'
                    metric = ast.literal_eval(
                        '{"name": "cpu.user_perc", '
                        '"dimensions": {'
                        '"k0": "v0",'
                        '"hostname": "Ibmserver"}'
                        '"timestamp", 1405630174123,'
                        '"value": 20,'
                        '"dimensions_hash": "ef3fb07027653934898bc9e3b908c29b"}')
                    self.kap._send_predictions(metric_id, metric)
                    self.assertEqual(self._metric_names, 'cpu.user_perc')
                    self.assertEqual(list(self.kap._timeseries)[0][0], '1405630174123')
                    self.assertEqual(list(self.kap._timeseries)[0][1], 20)
                    self.assertEqual(metric['name'], 'cpu.user_perc.ks.anomaly_score')
                    self.assertEqual(metric['value'], 0)

