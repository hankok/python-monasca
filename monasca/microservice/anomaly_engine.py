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
from oslo.config import cfg
from stevedore import driver
from monasca.common import kafka_conn
from monasca.common import namespace
from monasca.openstack.common import log
from monasca.openstack.common import service as os_service

ANOMALY_ENGINE_OPTS = [
    cfg.StrOpt('topic',
               default='metrics',
               help='The topic that messages will be retrieved from.'),
    cfg.StrOpt('processor',
               default='ks_anomaly_processor',
               help=('The message processer to load to process the message.'
                     'If the message does not need to be process anyway,'
                     'leave the default')),
]

cfg.CONF.register_opts(ANOMALY_ENGINE_OPTS, group="anomalyengine")

LOG = log.getLogger(__name__)


class AnomalyEngine(os_service.Service):

    def __init__(self, threads=1000):
        super(AnomalyEngine, self).__init__(threads)
        self._kafka_conn = kafka_conn.KafkaConnection(
            cfg.CONF.anomalyengine.topic)

        if cfg.CONF.anomalyengine.processor:
            self.ks_anomaly_processor = driver.DriverManager(
                namespace.PROCESSOR_NS,
                cfg.CONF.anomalyengine.processor,
                invoke_on_load=True,
                invoke_kwds={}).driver
            LOG.debug(dir(self.ks_anomaly_processor))
        else:
            self.ks_anomaly_processor = None

    def start(self):
        while True:
            try:
                for msg in self._kafka_conn.get_messages():
                    if msg and msg.message:
                        LOG.debug("Message received for alarm: " + msg.message.value)
                        msg_value = msg.message.value
                        if msg_value:
                            '''msg_value's format is:
                            {
                            'name': 'cpu.user_perc',
                            'dimensions': {
                                'k0': 'v0',
                                'hostname': 'Ibmserver'
                            },
                            'timestamp': 1405630174123,
                            'value': 20,
                            'dimensions_hash': ef3fb07027653934898bc9e3b908c29b
                            }
                            '''
                            # convert to dict
                            dict_metric = ast.literal_eval(msg_value)
                            (self.ks_anomaly_processor.
                                handle_prediction(dict_metric))
                # if autocommit is set, this will be a no-op call.
                self._kafka_conn.commit()
            except Exception:
                LOG.exception('Error occurred while handling kafka messages.')

    def stop(self):
        self._kafka_conn.close()
        super(AnomalyEngine, self).stop()
