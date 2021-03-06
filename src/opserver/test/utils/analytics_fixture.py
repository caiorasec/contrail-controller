#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

import socket
import fixtures
import subprocess
from util import retry
from mockredis import mockredis
import redis
import urllib2
import copy
import os
from operator import itemgetter
from opserver_introspect_utils import VerificationOpsSrv
from collector_introspect_utils import VerificationCollector

class Collector(object):
    def __init__(self, analytics_fixture, logger, is_dup=False):
        self.analytics_fixture = analytics_fixture
        self.listen_port = AnalyticsFixture.get_free_port()
        self.http_port = AnalyticsFixture.get_free_port()
        self.hostname = socket.gethostname()
        self._instance = None
        self._logger = logger
        self._is_dup = is_dup
        if self._is_dup is True:
            self.hostname = self.hostname+'dup'
    # end __init__

    def get_addr(self):
        return '127.0.0.1:'+str(self.listen_port)
    # end get_addr

    def start(self):
        assert(self._instance == None)
        self._log_file = '/tmp/vizd.messages.' + str(self.listen_port)
        args = [self.analytics_fixture.builddir + '/analytics/vizd',
            '--cassandra-server-list', '127.0.0.1:' +
            str(self.analytics_fixture.cassandra_port),
            '--redis-sentinel-port', 
            str(self.analytics_fixture.redis_sentinel_port),
            '--listen-port', str(self.listen_port),
            '--http-server-port', str(self.http_port),
            '--log-file', self._log_file]
        if self._is_dup is True:
            args.append('--dup')
        self._instance = subprocess.Popen(args, stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE)
        self._logger.info('Setting up Vizd: 127.0.0.1:%d' % (self.listen_port)) 
    # end start

    def stop(self):
        if self._instance is not None:
            self._logger.info('Shutting down Vizd: 127.0.0.1:%d' 
                              % (self.listen_port))
            self._instance.terminate()
            (vizd_out, vizd_err) = self._instance.communicate()
            vcode = self._instance.returncode
            if vcode != 0:
                self._logger.info('vizd returned %d' % vcode)
                self._logger.info('vizd terminated stdout: %s' % vizd_out)
                self._logger.info('vizd terminated stderr: %s' % vizd_err)
            subprocess.call(['rm', self._log_file])
            assert(vcode == 0)
            self._instance = None
    # end stop

# end class Collector

class OpServer(object):
    def __init__(self, primary_collector, secondary_collector, redis_port, 
                 analytics_fixture, logger, is_dup=False):
        self.primary_collector = primary_collector
        self.secondary_collector = secondary_collector
        self.analytics_fixture = analytics_fixture
        self.listen_port = AnalyticsFixture.get_free_port()
        self.http_port = AnalyticsFixture.get_free_port()
        self._redis_port = redis_port
        self._instance = None
        self._logger = logger
        self._is_dup = is_dup
    # end __init__

    def set_primary_collector(self, collector):
        self.primary_collector = collector
    # end set_primary_collector

    def set_secondary_collector(self, collector):
        self.secondary_collector = collector
    # end set_secondary_collector

    def start(self):
        assert(self._instance == None)
        openv = copy.deepcopy(os.environ)
        openv['PYTHONPATH'] = self.analytics_fixture.builddir + \
            '/sandesh/library/python'
        self._log_file = '/tmp/opserver.messages.' + str(self.listen_port)
        args = ['python', self.analytics_fixture.builddir + \
                '/opserver/opserver/opserver.py',
                '--redis_server_port', str(self._redis_port),
                '--redis_query_port', 
                str(self.analytics_fixture.redis_query.port),
                '--redis_sentinel_port', 
                str(self.analytics_fixture.redis_sentinel_port),
                '--http_server_port', str(self.http_port),
                '--log_file', self._log_file,
                '--rest_api_port', str(self.listen_port),
                '--collectors', self.primary_collector]
        if self.secondary_collector is not None:
            args.append(self.secondary_collector)
        if self._is_dup:
            args.append('--dup')

        self._instance = subprocess.Popen(args, env=openv,
                                          stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE)
        self._logger.info('Setting up OpServer: %s' % ' '.join(args))
    # end start

    def stop(self):
        if self._instance is not None:
            self._logger.info('Shutting down OpServer 127.0.0.1:%d' 
                              % (self.listen_port))
            self._instance.terminate()
            (op_out, op_err) = self._instance.communicate()
            ocode = self._instance.returncode
            if ocode != 0:
                self._logger.info('OpServer returned %d' % ocode)
                self._logger.info('OpServer terminated stdout: %s' % op_out)
                self._logger.info('OpServer terminated stderr: %s' % op_err)
            subprocess.call(['rm', self._log_file])
            self._instance = None
    # end stop

# end class OpServer

class QueryEngine(object):
    def __init__(self, primary_collector, secondary_collector, 
                 analytics_fixture, logger):
        self.primary_collector = primary_collector
        self.secondary_collector = secondary_collector
        self.analytics_fixture = analytics_fixture
        self.listen_port = AnalyticsFixture.get_free_port()
        self.http_port = AnalyticsFixture.get_free_port()
        self._instance = None
        self._logger = logger
    # end __init__

    def set_primary_collector(self, collector):
        self.primary_collector = collector
    # end set_primary_collector

    def set_secondary_collector(self, collector):
        self.secondary_collector = collector
    # end set_secondary_collector

    def start(self, analytics_start_time=None):
        assert(self._instance == None)
        self._log_file = '/tmp/qed.messages.' + str(self.listen_port)
        args = [self.analytics_fixture.builddir + '/query_engine/qedt',
                '--redis-port', str(self.analytics_fixture.redis_query.port),
                '--cassandra-server-list', '127.0.0.1:' +
                str(self.analytics_fixture.cassandra_port),
                '--http-server-port', str(self.listen_port),
                '--log-local', '--log-level', 'SYS_DEBUG',
                '--log-file', self._log_file,
                '--collectors', self.primary_collector]
        if self.secondary_collector is not None:
            args.append(self.secondary_collector)
        if analytics_start_time is not None:
            args += ['--start-time', str(analytics_start_time)]
        self._instance = subprocess.Popen(args,
                                          stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE)
        self._logger.info('Setting up QueryEngine: %s' % ' '.join(args))
    # end start

    def stop(self):
        if self._instance is not None:
            self._logger.info('Shutting down QueryEngine: 127.0.0.1:%d'
                              % (self.listen_port))
            self._instance.terminate()
            (qe_out, qe_err) = self._instance.communicate()
            rcode = self._instance.returncode
            if rcode != 0:
                self._logger.info('QueryEngine returned %d' % rcode)
                self._logger.info('QueryEngine terminated stdout: %s' % qe_out)
                self._logger.info('QueryEngine terminated stderr: %s' % qe_err)
            subprocess.call(['rm', self._log_file])
            assert(rcode == 0)
            self._instance = None
    # end stop

# end class QueryEngine

class Redis(object):
    def __init__(self, master_port=None):
        self.port = AnalyticsFixture.get_free_port()
        self.master_port = master_port
        self.running = False
    # end __init__

    def start(self):
        assert(self.running == False)
        self.running = True
        mockredis.start_redis(self.port, self.master_port) 
    # end start

    def stop(self):
        if self.running:
            mockredis.stop_redis(self.port)
            self.running =  False
    #end stop

# end class Redis

class AnalyticsFixture(fixtures.Fixture):

    def __init__(self, logger, builddir, cassandra_port, 
                 noqed=False, collector_ha_test=False, 
                 redis_ha_test=False): 
        self.builddir = builddir
        self.cassandra_port = cassandra_port
        self.logger = logger
        self.noqed = noqed
        self.collector_ha_test = collector_ha_test
        self.redis_ha_test = redis_ha_test

    def setUp(self):
        super(AnalyticsFixture, self).setUp()

        self.redis_uve_master = Redis()
        self.redis_uve_master.start()
        if self.redis_ha_test:
            self.redis_uve_slave = Redis(self.redis_uve_master.port)
            self.redis_uve_slave.start()
        self.redis_query = Redis()
        self.redis_query.start()
        self.redis_sentinel_port = AnalyticsFixture.get_free_port()
        mockredis.start_redis_sentinel(self.redis_sentinel_port,
                                       self.redis_uve_master.port)

        self.collectors = [Collector(self, self.logger)] 
        self.collectors[0].start()

        self.opserver_port = None
        if self.verify_collector_gen(self.collectors[0]):
            primary_collector = self.collectors[0].get_addr()
            secondary_collector = None
            if self.collector_ha_test:
                self.collectors.append(Collector(self, self.logger, True))
                self.collectors[1].start()
                secondary_collector = self.collectors[1].get_addr()
            self.opserver = OpServer(primary_collector, secondary_collector, 
                                     self.redis_uve_master.port, 
                                     self, self.logger)
            self.opserver.start()
            self.opserver_port = self.opserver.listen_port
            if self.redis_ha_test:
                self.opserver_dup = OpServer(primary_collector, 
                                             secondary_collector,
                                             self.redis_uve_slave.port, 
                                             self, self.logger)
                self.opserver_dup.start()
            self.query_engine = QueryEngine(primary_collector, 
                                            secondary_collector, 
                                            self, self.logger)
            if not self.noqed:
                self.query_engine.start()
    # end setUp

    def get_collector(self):
        return '127.0.0.1:'+str(self.collectors[0].listen_port)
    # end get_collector

    def get_collectors(self):
        return ['127.0.0.1:'+str(self.collectors[0].listen_port), 
                '127.0.0.1:'+str(self.collectors[1].listen_port)]
    # end get_collectors 

    def get_opserver_port(self):
        return self.opserver.listen_port
    # end get_opserver_port

    def verify_on_setup(self):
        result = True
        if self.opserver_port is None:
            result = result and False
            self.logger.error("Collector UVE not in Redis")
        if self.opserver_port is None:
            result = result and False
            self.logger.error("OpServer not started")
        if not self.verify_opserver_api():
            result = result and False
            self.logger.error("OpServer not responding")
        self.verify_is_run = True
        return result

    @retry(delay=2, tries=20)
    def verify_collector_gen(self, collector):
        '''
        See if the SandeshClient within vizd has been able to register
        with the collector within vizd
        '''
        vcl = VerificationCollector('127.0.0.1', collector.http_port)
        try:
            genlist = vcl.get_generators()['generators']
            src = genlist[0]['source']
        except:
            return False

        self.logger.info("Src Name is %s" % src)
        if src == socket.gethostname():
            return True
        else:
            return False

    @retry(delay=1, tries=10)
    def verify_opserver_api(self):
        '''
        Verify that the opserver is accepting client requests
        '''
        data = {}
        url = 'http://127.0.0.1:' + str(self.opserver_port) + '/'
        try:
            data = urllib2.urlopen(url).read()
        except urllib2.HTTPError, e:
            self.logger.info("HTTP error: %d" % e.code)
        except urllib2.URLError, e:
            self.logger.info("Network error: %s" % e.reason.args[1])

        self.logger.info("Checking OpServer %s" % str(data))
        if data == {}:
            return False
        else:
            return True

    @retry(delay=2, tries=10)
    def verify_collector_obj_count(self):
        vns = VerificationOpsSrv('127.0.0.1', self.opserver_port)
        res = vns.post_query('ObjectCollectorInfo',
                             start_time='-10m', end_time='now',
                             select_fields=["ObjectLog"],
                             where_clause=str(
                                 'ObjectId=' + socket.gethostname()),
                             sync=False)
        if res == []:
            return False
        else:
            assert(len(res) > 0)
            self.logger.info(str(res))
            return True

    @retry(delay=1, tries=10)
    def verify_generator_list(self, collector, exp_genlist):
        vcl = VerificationCollector('127.0.0.1', collector.http_port)
        try:
            genlist = vcl.get_generators()['generators']
            self.logger.info('generator list: ' + str(genlist))
            self.logger.info('exp generator list: ' + str(exp_genlist))
            if len(genlist) != len(exp_genlist):
                return False
            for mod in exp_genlist:
                gen_found = False
                for gen in genlist:
                    if mod == gen['module_id']:
                        gen_found = True
                        if gen['state'] != 'Established':
                            return False
                        break
                if gen_found is not True:
                    return False
        except Exception as err:
            self.logger.error('Exception: %s' % err)
            return False
        return True

    @retry(delay=3, tries=10)
    def verify_collector_redis_uve_master(self, collector, 
                                          exp_redis_uve_master):
        vcl = VerificationCollector('127.0.0.1', collector.http_port)
        try:
            redis_uve_master = vcl.get_redis_uve_master()['RedisUveMasterInfo']
            self.logger.info('redis uve master: ' + str(redis_uve_master))
            self.logger.info('exp redis uve master: 127.0.0.1:%d' % 
                             (exp_redis_uve_master.port))
            if int(redis_uve_master['port']) != exp_redis_uve_master.port:
                return False
            if redis_uve_master['status'] != 'Connected':
                return False
        except Exception as err:
            self.logger.error('Exception: %s' % err)
            return False
        return True

    @retry(delay=3, tries=10)
    def verify_opserver_redis_uve_master(self, opserver,
                                         exp_redis_uve_master):
        vop = VerificationOpsSrv('127.0.0.1', opserver.http_port) 
        try:
            redis_uve_master = vop.get_redis_uve_master()['RedisUveMasterInfo']
            self.logger.info('redis uve master: ' + str(redis_uve_master))
            self.logger.info('exp redis uve master: 127.0.0.1:%d' % 
                             (exp_redis_uve_master.port))
            if int(redis_uve_master['port']) != exp_redis_uve_master.port:
                return False
            if redis_uve_master['status'] != 'Connected':
                return False
        except Exception as err:
            self.logger.error('Exception: %s' % err)
            return False
        return True

    @retry(delay=1, tries=6)
    def verify_message_table_messagetype(self):
        self.logger.info("verify_message_table_messagetype")
        vns = VerificationOpsSrv('127.0.0.1', self.opserver_port)
        # query for CollectorInfo logs
        res = vns.post_query('MessageTable',
                             start_time='-10m', end_time='now',
                             select_fields=["ModuleId"],
                             where_clause="Messagetype = CollectorInfo")
        if (res == []):
            return False
        assert(len(res) > 0)

        # verify if the result returned is ok
        moduleids = list(set(x['ModuleId'] for x in res))
        self.logger.info("Modules: %s " % str(moduleids))
        # only one moduleid: Collector
        if (not((len(moduleids) == 1))):
            return False
        if (not ("Collector" in moduleids)):
            return False
        return True

    @retry(delay=1, tries=6)
    def verify_message_table_moduleid(self):
        self.logger.info("verify_message_table_moduleid")
        vns = VerificationOpsSrv('127.0.0.1', self.opserver_port)
        # query for QueryEngine logs
        res_qe = vns.post_query('MessageTable',
                                start_time='-10m', end_time='now',
                                select_fields=["Type", "Messagetype"],
                                where_clause="ModuleId = QueryEngine")
        # query for Collector logs
        res_c = vns.post_query('MessageTable',
                               start_time='-10m', end_time='now',
                               select_fields=["Type", "Messagetype"],
                               where_clause="ModuleId = Collector")
        if (res_qe == []) or (res_c == []):
            return False
        assert(len(res_qe) > 0)
        assert(len(res_c) > 0)
        return True

    @retry(delay=1, tries=6)
    def verify_message_table_where_or(self):
        self.logger.info("verify_message_table_where_or")
        vns = VerificationOpsSrv('127.0.0.1', self.opserver_port)
        where_clause1 = "ModuleId = QueryEngine"
        where_clause2 = str("Source =" + socket.gethostname())
        res = vns.post_query(
            'MessageTable',
            start_time='-10m', end_time='now',
            select_fields=["ModuleId"],
            where_clause=str(where_clause1 + " OR  " + where_clause2))
        if res == []:
            return False
        else:
            assert(len(res) > 0)
            moduleids = list(set(x['ModuleId'] for x in res))
            self.logger.info(str(moduleids))
            if ('Collector' in moduleids) and ('QueryEngine' in moduleids):
                return True
            else:
                return False

    @retry(delay=1, tries=6)
    def verify_message_table_where_and(self):
        self.logger.info("verify_message_table_where_and")
        vns = VerificationOpsSrv('127.0.0.1', self.opserver_port)
        where_clause1 = "ModuleId = QueryEngine"
        where_clause2 = str("Source =" + socket.gethostname())
        res = vns.post_query(
            'MessageTable',
            start_time='-10m', end_time='now',
            select_fields=["ModuleId"],
            where_clause=str(where_clause1 + " AND  " + where_clause2))
        if res == []:
            return False
        else:
            assert(len(res) > 0)
            moduleids = list(set(x['ModuleId'] for x in res))
            self.logger.info(str(moduleids))
            if len(moduleids) == 1:  # 1 moduleid: QueryEngine
                return True
            else:
                return False

    @retry(delay=1, tries=6)
    def verify_message_table_filter(self):
        self.logger.info("verify_message_table_where_filter")
        vns = VerificationOpsSrv('127.0.0.1', self.opserver_port)
        where_clause1 = "ModuleId = QueryEngine"
        where_clause2 = str("Source =" + socket.gethostname())
        res = vns.post_query('MessageTable',
                             start_time='-10m', end_time='now',
                             select_fields=["ModuleId"],
                             where_clause=str(
                                 where_clause1 + " OR  " + where_clause2),
                             filter="ModuleId = QueryEngine")
        if res == []:
            return False
        else:
            assert(len(res) > 0)
            moduleids = list(set(x['ModuleId'] for x in res))
            self.logger.info(str(moduleids))
            if len(moduleids) != 1:  # 1 moduleid: Collector
                return False

        res1 = vns.post_query('MessageTable',
                              start_time='-10m', end_time='now',
                              select_fields=["ModuleId"],
                              where_clause=str(
                                  where_clause1 + " AND  " + where_clause2),
                              filter="ModuleId = Collector")
        self.logger.info(str(res1))
        if res1 != []:
            return False
        return True

    @retry(delay=1, tries=1)
    def verify_message_table_sort(self):
        self.logger.info("verify_message_table_sort:Ascending Sort")
        vns = VerificationOpsSrv('127.0.0.1', self.opserver_port)
        where_clause1 = "ModuleId = QueryEngine"
        where_clause2 = str("Source =" + socket.gethostname())

        exp_moduleids = ['Collector', 'OpServer', 'QueryEngine']

        # Ascending sort
        res = vns.post_query('MessageTable',
                             start_time='-10m', end_time='now',
                             select_fields=["ModuleId"],
                             where_clause=str(
                                 where_clause1 + " OR  " + where_clause2),
                             sort_fields=["ModuleId"], sort=1)
        if res == []:
            return False
        else:
            assert(len(res) > 0)
            moduleids = []
            for x in res:
                if x['ModuleId'] not in moduleids:
                    moduleids.append(x['ModuleId'])
            self.logger.info(str(moduleids))
            for module in exp_moduleids:
                if module not in moduleids:
                    return False
            expected_res = sorted(res, key=itemgetter('ModuleId'))
            if res != expected_res:
                return False

        # Descending sort
        self.logger.info("verify_message_table_sort:Descending Sort")
        res = vns.post_query('MessageTable',
                             start_time='-10m', end_time='now',
                             select_fields=["ModuleId"],
                             where_clause=str(
                                 where_clause1 + " OR  " + where_clause2),
                             sort_fields=["ModuleId"], sort=2)
        if res == []:
            return False
        else:
            assert(len(res) > 0)
            moduleids = []
            for x in res:
                if x['ModuleId'] not in moduleids:
                    moduleids.append(x['ModuleId'])
            self.logger.info(str(moduleids))
            for module in exp_moduleids:
                if module not in moduleids:
                    return False
            expected_res = sorted(
                res, key=itemgetter('ModuleId'), reverse=True)
            if res != expected_res:
                return False

        # Limit
        res = vns.post_query('MessageTable',
                             start_time='-10m', end_time='now',
                             select_fields=["ModuleId"],
                             where_clause=str(
                                 where_clause1 + " OR  " + where_clause2),
                             sort_fields=["ModuleId"], sort=1, limit=1)
        if res == []:
            return False
        else:
            assert(len(res) > 0)
            moduleids = []
            for x in res:
                if x['ModuleId'] not in moduleids:
                    moduleids.append(x['ModuleId'])
            self.logger.info(str(moduleids))
            if len(moduleids) == 1:  # 2 moduleids: Collector/QueryEngine
                if moduleids[0] != 'Collector':
                    return False
                return True
            else:
                return False

    @retry(delay=1, tries=8)
    def verify_intervn_all(self, gen_obj):
        self.logger.info("verify_intervn_all")
        vns = VerificationOpsSrv('127.0.0.1', self.opserver_port)
        res = vns.post_query('StatTable.UveVirtualNetworkAgent.vn_stats',
                             start_time='-10m',
                             end_time='now',
                             select_fields=['T', 'name', 'vn_stats.other_vn', 'vn_stats.vrouter', 'vn_stats.in_tpkts'],
                             where_clause=gen_obj.vn_all_rows['whereclause'])
        self.logger.info(str(res))
        if len(res) == gen_obj.vn_all_rows['rows']:
            return True
        return False      

    @retry(delay=1, tries=8)
    def verify_intervn_sum(self, gen_obj):
        self.logger.info("verify_intervn_sum")
        vns = VerificationOpsSrv('127.0.0.1', self.opserver_port)
        res = vns.post_query('StatTable.UveVirtualNetworkAgent.vn_stats',
                             start_time='-10m',
                             end_time='now',
                             select_fields=gen_obj.vn_sum_rows['select'],
                             where_clause=gen_obj.vn_sum_rows['whereclause'])
        self.logger.info(str(res))
        if len(res) == gen_obj.vn_sum_rows['rows']:
            return True
        return False 

    @retry(delay=1, tries=10)
    def verify_flow_samples(self, generator_obj):
        self.logger.info("verify_flow_samples")
        vns = VerificationOpsSrv('127.0.0.1', self.opserver_port)
        res = vns.post_query('FlowSeriesTable',
                             start_time=str(generator_obj.flow_start_time),
                             end_time=str(generator_obj.flow_end_time),
                             select_fields=['T'], where_clause='')
        self.logger.info(str(res))
        if len(res) == generator_obj.num_flow_samples:
            return True
        return False
    # end verify_flow_samples

    def verify_flow_table(self, generator_obj):
        # query flow records
        self.logger.info('verify_flow_table')
        vns = VerificationOpsSrv('127.0.0.1', self.opserver_port)
        res = vns.post_query('FlowRecordTable',
                             start_time=str(generator_obj.flow_start_time),
                             end_time=str(generator_obj.flow_end_time),
                             select_fields=[
                                 'UuidKey', 'agg-packets', 'agg-bytes'],
                             where_clause='')
        self.logger.info("FlowRecordTable result:%s" % str(res))
        assert(len(res) == generator_obj.flow_cnt)

        # query based on various WHERE parameters

        # sourcevn and sourceip
        res = vns.post_query(
            'FlowRecordTable',
            start_time=str(generator_obj.flow_start_time),
            end_time=str(generator_obj.flow_end_time),
            select_fields=['UuidKey', 'sourcevn', 'sourceip'],
            where_clause='sourceip=10.10.10.1 AND sourcevn=domain1:admin:vn1')
        self.logger.info(str(res))
        assert(len(res) == generator_obj.flow_cnt)
        res = vns.post_query(
            'FlowSeriesTable',
            start_time=str(generator_obj.flow_start_time),
            end_time=str(generator_obj.flow_end_time),
            select_fields=['sourcevn', 'sourceip'],
            where_clause='sourceip=10.10.10.1 AND sourcevn=domain1:admin:vn1')
        self.logger.info(str(res))
        assert(len(res) == generator_obj.num_flow_samples)
        # give non-existent values in the where clause
        res = vns.post_query('FlowRecordTable',
                             start_time=str(generator_obj.flow_start_time),
                             end_time=str(generator_obj.flow_end_time),
                             select_fields=['UuidKey', 'sourcevn', 'sourceip'],
                             where_clause='sourceip=20.1.1.10')
        self.logger.info(str(res))
        assert(len(res) == 0)
        res = vns.post_query(
            'FlowSeriesTable',
            start_time=str(generator_obj.flow_start_time),
            end_time=str(generator_obj.flow_end_time),
            select_fields=['sourcevn', 'sourceip'],
            where_clause='sourceip=20.1.1.10 AND sourcevn=domain1:admin:vn1')
        self.logger.info(str(res))
        assert(len(res) == 0)

        # destvn and destip
        res = vns.post_query(
            'FlowRecordTable',
            start_time=str(generator_obj.flow_start_time),
            end_time=str(generator_obj.flow_end_time),
            select_fields=['UuidKey', 'destvn', 'destip'],
            where_clause='destip=10.10.10.2 AND destvn=domain1:admin:vn2')
        self.logger.info(str(res))
        assert(len(res) == generator_obj.flow_cnt)
        res = vns.post_query(
            'FlowSeriesTable',
            start_time=str(generator_obj.flow_start_time),
            end_time=str(generator_obj.flow_end_time),
            select_fields=['destvn', 'destip'],
            where_clause='destip=10.10.10.2 AND destvn=domain1:admin:vn2')
        self.logger.info(str(res))
        assert(len(res) == generator_obj.num_flow_samples)
        # give non-existent values in the where clause
        res = vns.post_query(
            'FlowRecordTable',
            start_time=str(generator_obj.flow_start_time),
            end_time=str(generator_obj.flow_end_time),
            select_fields=['UuidKey', 'destvn', 'destip'],
            where_clause='destip=10.10.10.2 AND ' +
            'destvn=default-domain:default-project:default-virtual-network')
        self.logger.info(str(res))
        assert(len(res) == 0)
        res = vns.post_query(
            'FlowSeriesTable',
            start_time=str(generator_obj.flow_start_time),
            end_time=str(generator_obj.flow_end_time),
            select_fields=['destvn', 'destip'],
            where_clause='destip=20.1.1.10 AND destvn=domain1:admin:vn2')
        self.logger.info(str(res))
        assert(len(res) == 0)

        # sport and protocol
        res = vns.post_query('FlowRecordTable',
                             start_time=str(generator_obj.flow_start_time),
                             end_time=str(generator_obj.flow_end_time),
                             select_fields=['UuidKey', 'sport', 'protocol'],
                             where_clause='sport=13 AND protocol=1')
        self.logger.info(str(res))
        assert(len(res) == 1)
        res = vns.post_query('FlowSeriesTable',
                             start_time=str(generator_obj.flow_start_time),
                             end_time=str(generator_obj.flow_end_time),
                             select_fields=['sport', 'protocol'],
                             where_clause='sport=13 AND protocol=1')
        self.logger.info(str(res))
        assert(len(res) == 5)
        # give no-existent values in the where clause
        res = vns.post_query('FlowRecordTable',
                             start_time=str(generator_obj.flow_start_time),
                             end_time=str(generator_obj.flow_end_time),
                             select_fields=['UuidKey', 'sport', 'protocol'],
                             where_clause='sport=20 AND protocol=17')
        self.logger.info(str(res))
        assert(len(res) == 0)
        res = vns.post_query('FlowSeriesTable',
                             start_time=str(generator_obj.flow_start_time),
                             end_time=str(generator_obj.flow_end_time),
                             select_fields=['sport', 'protocol'],
                             where_clause='sport=20 AND protocol=1')
        self.logger.info(str(res))
        assert(len(res) == 0)

        # dport and protocol
        res = vns.post_query('FlowRecordTable',
                             start_time=str(generator_obj.flow_start_time),
                             end_time=str(generator_obj.flow_end_time),
                             select_fields=['UuidKey', 'dport', 'protocol'],
                             where_clause='dport=104 AND protocol=2')
        self.logger.info(str(res))
        assert(len(res) == 1)
        res = vns.post_query('FlowSeriesTable',
                             start_time=str(generator_obj.flow_start_time),
                             end_time=str(generator_obj.flow_end_time),
                             select_fields=['dport', 'protocol'],
                             where_clause='dport=104 AND protocol=2')
        self.logger.info(str(res))
        assert(len(res) == 5)
        # give no-existent values in the where clause
        res = vns.post_query('FlowRecordTable',
                             start_time=str(generator_obj.flow_start_time),
                             end_time=str(generator_obj.flow_end_time),
                             select_fields=['UuidKey', 'dport', 'protocol'],
                             where_clause='dport=10 AND protocol=17')
        self.logger.info(str(res))
        assert(len(res) == 0)
        res = vns.post_query('FlowSeriesTable',
                             start_time=str(generator_obj.flow_start_time),
                             end_time=str(generator_obj.flow_end_time),
                             select_fields=['dport', 'protocol'],
                             where_clause='dport=10 AND protocol=17')
        self.logger.info(str(res))
        assert(len(res) == 0)

        # sort and limit
        res = vns.post_query(
            'FlowRecordTable',
            start_time=str(generator_obj.flow_start_time),
            end_time=str(generator_obj.flow_end_time),
            select_fields=['UuidKey', 'protocol'], where_clause='',
            sort_fields=['protocol'], sort=1)
        self.logger.info(str(res))
        assert(len(res) == generator_obj.flow_cnt)
        assert(res[0]['protocol'] == 0)

        res = vns.post_query('FlowRecordTable',
                             start_time=str(generator_obj.flow_start_time),
                             end_time=str(generator_obj.flow_end_time),
                             select_fields=['protocol'], where_clause='',
                             sort_fields=['protocol'], sort=2, limit=1)
        self.logger.info(str(res))
        assert(len(res) == 1)
        assert(res[0]['protocol'] == 2)

        return True
    # end verify_flow_table

    def verify_flow_series_aggregation_binning(self, generator_obj):
        self.logger.info('verify_flow_series_aggregation_binning')
        vns = VerificationOpsSrv('127.0.0.1', self.opserver_port)

        # 1. stats
        self.logger.info('Flowseries: [sum(bytes), sum(packets), flow_count]')
        res = vns.post_query(
            'FlowSeriesTable',
            start_time=str(generator_obj.flow_start_time),
            end_time=str(generator_obj.flow_end_time),
            select_fields=['sum(bytes)', 'sum(packets)', 'flow_count'], 
            where_clause='')
        self.logger.info(str(res))
        assert(len(res) == 1)
        exp_sum_pkts = exp_sum_bytes = 0
        for f in generator_obj.flows:
            exp_sum_pkts += f.packets
            exp_sum_bytes += f.bytes
        assert(res[0]['sum(packets)'] == exp_sum_pkts)
        assert(res[0]['sum(bytes)'] == exp_sum_bytes)
        assert(res[0]['flow_count'] == generator_obj.flow_cnt)

        # 2. flow tuple + stats
        self.logger.info(
            'Flowseries: [sport, dport, sum(bytes), sum(packets), flow_count]')
        # Each flow has unique (sport, dport). Therefore, the following query
        # should return # records equal to the # flows.
        res = vns.post_query(
            'FlowSeriesTable',
            start_time=str(generator_obj.flow_start_time),
            end_time=str(generator_obj.flow_end_time),
            select_fields=['sport', 'dport', 'sum(bytes)', 
                           'sum(packets)', 'flow_count'],
            where_clause='')
        self.logger.info(str(res))
        assert(len(res) == generator_obj.flow_cnt)
        for r in res:
            cnt = 0
            for f in generator_obj.flows:
                if r['sport'] == f.sport and r['dport'] == f.dport:
                    assert(r['sum(packets)'] == f.packets)
                    assert(r['sum(bytes)'] == f.bytes)
                    assert(r['flow_count'] == 1)
                    break
                cnt += 1
            assert(cnt < generator_obj.flow_cnt)

        # All flows has the same (sourcevn, destvn). Therefore, the following
        # query should return one record.
        res = vns.post_query(
            'FlowSeriesTable',
            start_time=str(generator_obj.flow_start_time),
            end_time=str(generator_obj.flow_end_time),
            select_fields=['sourcevn', 'destvn', 'sum(bytes)', 
                           'sum(packets)', 'flow_count'],
            where_clause='')
        self.logger.info(str(res))
        assert(len(res) == 1)
        exp_sum_pkts = exp_sum_bytes = 0
        for f in generator_obj.flows:
            exp_sum_pkts += f.packets
            exp_sum_bytes += f.bytes
        assert(res[0]['sum(packets)'] == exp_sum_pkts)
        assert(res[0]['sum(bytes)'] == exp_sum_bytes)
        assert(res[0]['flow_count'] == generator_obj.flow_cnt)

        # top 3 flows
        res = vns.post_query('FlowSeriesTable',
                             start_time=str(generator_obj.flow_start_time),
                             end_time=str(generator_obj.flow_end_time),
                             select_fields=['sport', 'dport', 'sum(bytes)'],
                             where_clause='',
                             sort_fields=['sum(bytes)'], sort=2, limit=3)
        self.logger.info(str(res))
        assert(len(res) == 3)
        exp_res = sorted(
            generator_obj.flows, key=lambda flow: flow.bytes, reverse=True)
        cnt = 0
        for r in res:
            assert(r['sport'] == exp_res[cnt].sport)
            assert(r['dport'] == exp_res[cnt].dport)
            assert(r['sum(bytes)'] == exp_res[cnt].bytes)
            cnt += 1

        # 3. T=<granularity> + stats
        self.logger.info('Flowseries: [T=<x>, sum(bytes), sum(packets)]')
        st = str(generator_obj.flow_start_time)
        et = str(generator_obj.flow_start_time + (30 * 1000 * 1000))
        granularity = 10
        res = vns.post_query(
            'FlowSeriesTable', start_time=st, end_time=et,
            select_fields=['T=%s' % (granularity), 'sum(bytes)',
                           'sum(packets)'],
            where_clause='sourcevn=domain1:admin:vn1 ' +
            'AND destvn=domain1:admin:vn2')
        self.logger.info(str(res))
        num_records = (int(et) - int(st)) / (granularity * 1000 * 1000)
        assert(len(res) == num_records)
        ts = [generator_obj.flow_start_time +
              ((x + 1) * granularity * 1000 * 1000)
              for x in range(num_records)]
        exp_result = {
            ts[0]: {'sum(bytes)': 5500, 'sum(packets)': 65},
            ts[1]: {'sum(bytes)': 725,  'sum(packets)': 15},
            ts[2]: {'sum(bytes)': 700,  'sum(packets)': 8}
        }
        assert(len(exp_result) == num_records)
        for r in res:
            try:
                stats = exp_result[r['T']]
            except KeyError:
                assert(False)
            assert(r['sum(bytes)'] == stats['sum(bytes)'])
            assert(r['sum(packets)'] == stats['sum(packets)'])

        # 4. T=<granularity> + tuples + stats
        self.logger.info(
            'Flowseries: [T=<x>, protocol, sum(bytes), sum(packets)]')
        st = str(generator_obj.flow_start_time)
        et = str(generator_obj.flow_start_time + (10 * 1000 * 1000))
        granularity = 5
        res = vns.post_query(
            'FlowSeriesTable', start_time=st, end_time=et,
            select_fields=['T=%s' % (granularity), 'protocol', 'sum(bytes)',
                           'sum(packets)'],
            where_clause='sourcevn=domain1:admin:vn1 ' +
            'AND destvn=domain1:admin:vn2')
        self.logger.info(str(res))
        num_ts = (int(et) - int(st)) / (granularity * 1000 * 1000)
        ts = [generator_obj.flow_start_time +
              ((x + 1) * granularity * 1000 * 1000) for x in range(num_ts)]
        exp_result = {
            0: {ts[0]: {'sum(bytes)': 450, 'sum(packets)': 5},
                ts[1]: {'sum(bytes)': 250, 'sum(packets)': 3}
                },
            1: {ts[0]: {'sum(bytes)': 1050, 'sum(packets)': 18},
                ts[1]: {'sum(bytes)': 750,  'sum(packets)': 14}
                },
            2: {ts[0]: {'sum(bytes)': 3000, 'sum(packets)': 25}
                }
        }
        assert(len(res) == 5)
        for r in res:
            try:
                stats = exp_result[r['protocol']][r['T']]
            except KeyError:
                assert(False)
            assert(r['sum(bytes)'] == stats['sum(bytes)'])
            assert(r['sum(packets)'] == stats['sum(packets)'])

        return True
    # end verify_flow_series_aggregation_binning

    def cleanUp(self):
        super(AnalyticsFixture, self).cleanUp()

        self.opserver.stop()
        self.query_engine.stop()
        for collector in self.collectors:
            collector.stop()
        self.redis_uve_master.stop()
        if self.redis_ha_test:
            self.redis_uve_slave.stop()
            self.opserver_dup.stop()
        self.redis_query.stop()
        mockredis.stop_redis_sentinel(self.redis_sentinel_port)

    @staticmethod
    def get_free_port():
        cs = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cs.bind(("", 0))
        cport = cs.getsockname()[1]
        cs.close()
        return cport
