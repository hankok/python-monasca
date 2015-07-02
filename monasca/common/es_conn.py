# Copyright 2012-2013 eNovance <licensing@enovance.com>
#
# Author: Tong Li <litong01@us.ibm.com>
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

import datetime
from oslo.config import cfg
import requests
import ujson as json

from monasca.common import strategy
from monasca.openstack.common import log


OPTS = [
    cfg.StrOpt('uri',
               help='Address to kafka server. For example: '
               'uri=http://192.168.1.191:9200/'),
    cfg.StrOpt('index_prefix',
               default='monasca_',
               help='The prefix for an index.'),
    cfg.StrOpt('time_id',
               default='timestamp',
               help='The type of the data.'),
    cfg.BoolOpt('drop_data',
                default=False,
                help=('Specify if received data should be simply dropped. '
                      'This parameter is only for testing purposes.')),
]

cfg.CONF.register_opts(OPTS, group="es")

LOG = log.getLogger(__name__)


class ESConnection(object):

    def __init__(self, doc_type):
        if not cfg.CONF.es.uri:
            raise Exception('ElasticSearch is not configured correctly! '
                            'Use configuration file to specify ElasticSearch '
                            'uri, for example: '
                            'uri=192.168.1.191:9200')

        self.uri = cfg.CONF.es.uri
        if self.uri.strip()[-1] != '/':
            self.uri += '/'
        self.index_prefix = cfg.CONF.es.index_prefix
        self.doc_type = doc_type
        self.time_id = cfg.CONF.es.time_id
        self.drop_data = cfg.CONF.es.drop_data

        self._index_strategy = strategy.IndexStrategy()

        day = datetime.datetime.now()
        index = self._index_strategy.get_index(day)
        self.post_path = '%s%s%s/%s/_bulk' % (self.uri, self.index_prefix,
                                              index, self.doc_type)
        self.base_path = '%s%s%s/%s' % (self.uri, self.index_prefix,
                                        index, self.doc_type)
        LOG.debug('ElasticSearch Connection initialized successfully!')

    def send_messages(self, msg):
        LOG.debug('Prepare to send messages.')
        if self.drop_data:
            return
        else:
            res = requests.post(self.post_path, data=msg)
            LOG.debug('Msg posted with response code: %s' % res.status_code)

    def get_messages(self, cond):
        LOG.debug('Prepare to get messages.')
        if cond:
            path = '%s%s%*/%s/_search' % (self.uri, self.index_prefix,
                                          self.doc_type)
            LOG.debug('Search path:', path)
            requests.post(path, data=json.dumps(cond))

    def get_message_by_id(self, id):
        LOG.debug('Prepare to get messages by id.')
        if self.drop_data:
            return ''
        else:
            path = self.base_path + '/_search?q=_id:' + id
            LOG.debug('Search path:' + path)
            res = requests.get(path)
            LOG.debug('Msg get with response code: %s' % res.status_code)
            return res

    def post_messages(self, msg, id):
        LOG.debug('Prepare to post messages.')
        if self.drop_data:
            return 204
        else:
            res = requests.post(self.base_path + '/' + id, data=msg)
            LOG.debug('Msg post with response code: %s' % res.status_code)
            return res.status_code

    def put_messages(self, msg, id):
        LOG.debug('Prepare to put messages.')
        if self.drop_data:
            return 204
        else:
            res = requests.put(self.base_path + '/' + id, data=msg)
            LOG.debug('Msg put with response code: %s' % res.status_code)
            return res.status_code

    def del_messages(self, id):
        LOG.debug('Prepare to delete messages.')
        if self.drop_data:
            return 204
        else:
            res = requests.delete(self.base_path + '/' + id)
            LOG.debug('Msg delete with response code: %s' % res.status_code)
            return res.status_code
