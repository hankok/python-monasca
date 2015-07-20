# Copyright (c) 2014 Hewlett-Packard Development Company, L.P.
# Copyright 2015 Carnegie Mellon University
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import ast
import collections
import scipy
import statsmodels.api as sm
import time
from monasca.common import kafka_conn
from monasca.openstack.common import log
from oslo.config import cfg

try:
    import ujson as json
except ImportError:
    import json

LOG = log.getLogger(__name__)
METRIC_NAME_SUFFIXES = ['.predicted', '.anomaly_score', '.anomaly_likelihood']

KS_ANOMALY_PROCESSOR_OPTS = [
    cfg.StrOpt('topic',
               default='metrics',
               help='The topic that messages will be retrieved from.'),
    cfg.StrOpt('names',
               default='cpu.user_perc, cpu.system_perc',
               help='metric names'),
    cfg.StrOpt('metric_name_suffix',
               default='.anomaly_score',
               help='the suffix to metric names that indicates it is processed'),
    cfg.IntOpt('reference_duration',
               default=3600,
               help=''),
    cfg.IntOpt('probe_duration',
               default=600,
               help=''),
    cfg.FloatOpt('ks_d',
               default=0.5),
    cfg.IntOpt('min_samples',
               default=15),
]

cfg.CONF.register_opts(KS_ANOMALY_PROCESSOR_OPTS, group="ksanomalyprocess")

class KsAnomalyProcessor(object):
    def __init__(self):
        LOG.debug('initializing KsAnomalyProcessor!')
        super(KsAnomalyProcessor, self).__init__()
        self._reference_duration = cfg.CONF.ksanomalyprocess.reference_duration
        self._probe_duration = cfg.CONF.ksanomalyprocess.probe_duration
        self._ks_d = cfg.CONF.ksanomalyprocess.ks_d
        self._min_samples = cfg.CONF.ksanomalyprocess.min_samples
        self._metric_name_suffix = cfg.CONF.ksanomalyprocess.metric_name_suffix
        self._metric_names = cfg.CONF.ksanomalyprocess.names
        self._timeseries = {}
        self._kafka_conn = kafka_conn.KafkaConnection(
            cfg.CONF.ksanomalyprocess.topic)

    def _send_predictions(self, metric_id, metric):
        if metric_id not in self._timeseries:
            self._timeseries[metric_id] = collections.deque(maxlen=256)

        time_series = self._timeseries[metric_id]
        time_series.append((metric['timestamp'], metric['value']))
        result = self._ks_test(time_series)
        metric_name = metric['name']
        metric['name'] = metric_name + '.ks.anomaly_score'
        metric['value'] = result
        processed_metic = json.dumps(metric)

        self._kafka_conn.send_messages(processed_metic)

    def _ks_test(self, timeseries):
        """
        A timeseries is anomalous if 2 sample Kolmogorov-Smirnov test indicates
        that data distribution for last 10 minutes is different from last hour.
        It produces false positives on non-stationary series so Augmented
        Dickey-Fuller test applied to check for stationarity.
        """
        now = int(time.time())
        reference_start_time = now - self._reference_duration
        probe_start_time = now - self._probe_duration

        reference = scipy.array([x[1] for x in timeseries if x[0] >= reference_start_time and
                                 x[0] < probe_start_time])
        probe = scipy.array([x[1] for x in timeseries if x[0] >= probe_start_time])

        if reference.size < self._min_samples or probe.size < self._min_samples:
            return 0.0

        ks_d, ks_p_value = scipy.stats.ks_2samp(reference, probe)

        if ks_p_value < 0.05 and ks_d > self._ks_d:
            results = sm.tsa.stattools.adfuller(reference)
            pvalue = results[1]
            if pvalue < 0.05:
                return 1.0

        return 0.0

    def handle_prediction(self, dict_metric):
        metric_name = dict_metric['name']

        if metric_name not in self._metric_names:
            return

        # exclude the processed metrics
        if any(suffix in metric_name for suffix in self._metric_name_suffix):
            return
        # dimension_hash is used to group same type of metrics
        metric_id = dimensions_hash = dict_metric['dimensions_hash']
        self._send_predictions(metric_id, dict_metric)
