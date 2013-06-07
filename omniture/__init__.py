import requests
import binascii
from datetime import datetime
import time
import sha
import json
import utils


class Value(object):
    def __init__(self, title, id, properties={}):
        self.title = title
        self.id = id

        for k, v in properties.items():
            setattr(self, k, v)

    @classmethod
    def list(self, name, items, title='title', id='id'):
        values = [Value(item[title], item[id], item) for item in items]
        return utils.AddressableList(values, name)

    def __repr__(self):
        return "<{title}: {id}>".format(**self.__dict__)


class Account(object):
    def __init__(self, endpoint='https://api.omniture.com/admin/1.3/rest/'):
        self.endpoint = endpoint

    def initialize(self):
        data = self.request('Company', 'GetReportSuites')['report_suites']
        suites = [Suite(suite['site_title'], suite['rsid'], self) for suite in data]
        self.suites = utils.AddressableList(suites)

    def request(self, api, method, query={}):
        response = requests.post(
            self.endpoint, 
            params={'method': api + '.' + method}, 
            data=json.dumps(query), 
            headers=self._build_token()
            )
        return response.json()

    def _serialize_header(self, properties):
        header = []
        for key, value in properties.items():
            header.append('{key}="{value}"'.format(key=key, value=value))
        return ', '.join(header)

    def _build_token(self):
        nonce = str(time.time())
        base64nonce = binascii.b2a_base64(binascii.a2b_qp(nonce))
        created_date = datetime.today().isoformat() + 'Z'
        sha_object = sha.new(nonce + created_date + self.secret)
        password_64 = binascii.b2a_base64(sha_object.digest())

        properties = {
            "Username": self.username, 
            "PasswordDigest": password_64.strip(),
            "Nonce": base64nonce.strip(),
            "Created": created_date,
        }
        header = 'UsernameToken ' + self._serialize_header(properties)

        return {'X-WSSE': header}

    def authenticate(self, username, secret=None, prefix='', suffix=''):
        if secret:
            self.username = username
            self.secret = secret
        else:
            source = username
            username = utils.affix(prefix, 'OMNITURE_USERNAME', suffix)
            secret = utils.affix(prefix, 'OMNITURE_SECRET', suffix)
            self.username = source[username]
            self.secret = source[secret]

        self.initialize()


class Suite(Value):
    def request(self, api, method, query={}):
        raw_query = {}
        raw_query.update(query)
        if 'reportDescription' in raw_query:
            raw_query['reportDescription']['reportSuiteID'] = self.id
        elif api == 'ReportSuite':
            raw_query['rsid_list'] = [self.id]

        return self.account.request(api, method, raw_query)

    def __init__(self, title, id, account):
        super(Suite, self).__init__(title, id)

        self.account = account

    @property
    @utils.memoize
    def metrics(self):
        data = self.request('ReportSuite', 'GetAvailableMetrics')[0]['available_metrics']
        return Value.list('metrics', data, 'display_name', 'metric_name')

    @property
    @utils.memoize
    def elements(self):
        data = self.request('ReportSuite', 'GetAvailableElements')[0]['available_elements']
        return Value.list('elements', data, 'display_name', 'element_name')

    @property
    @utils.memoize
    def evars(self):
        data = self.request('ReportSuite', 'GetEVars')[0]['evars']
        return Value.list('evars', data, 'name', 'evar_num')

    @property
    @utils.memoize
    def segments(self):
        data = self.request('ReportSuite', 'GetSegments')[0]['sc_segments']
        return Value.list('segments', data, 'name', 'id')

    @property
    def report(self):
        return Query(self)


class Query(object):
    def __init__(self, suite):
        self.suite = suite
        self.raw = {}
        self.id = None

    def _get_key(self, value, category, expand=False):
        if not isinstance(value, Value):
            value = getattr(self.suite, category)[value]

        if expand:
            kv = {}
            kv[expand] = value.id
            return kv
        else:
            return value.id

    def range(self, start, stop=None, granularity='day'):
        stop = stop or start

        if start == stop:
            self.raw['date'] = start
        else:
            self.raw.update({
                'dateFrom': start,
                'dateTo': stop,
            })

        self.raw['dateGranularity'] = granularity

        return self

    def raw(self, properties):
        self.raw.update(properties)
        return self

    def set(self, key, value):
        self.raw[key] = value
        return self

    def sort(self, facet):
        #self.raw['sortBy'] = facet
        raise NotImplementedError()
        return self

    def filter(self, segment=None, element=None):
        if segment:
            self.raw['segment_id'] = self._get_key(segment, 'segments')

        if element:
            raise NotImplementedError()

        return self

    def ranked(self, metric):
        self.raw['metrics'] = [self._get_key(metric, 'metrics', expand='id')]
        self.method = 'QueueRanked'
        return self

    def trended(self, metric, element):
        self.method = 'QueueTrended'
        return self

    def over_time(self, metrics):
        self.method = 'QueueOvertime'
        self.raw['metrics'] = [self._get_key(metric, 'metrics', expand='id') for metric in metrics]
        return self

    def build(self):
        return {'reportDescription': self.raw}

    def queue(self):
        q = self.build()
        self.id = self.suite.request('Report', self.method, q)['reportID']
        return self

    def probe(self, fn, heartbeat=None, interval=1):
        status = ''
        while status not in ['done', 'ready']:
            if heartbeat:
                heartbeat()
            time.sleep(interval)
            response = fn()
            status = response['status']

        return response

    def sync(self, heartbeat=None, interval=1):
        if not self.id:
            self.queue()

        # this looks clunky, but Omniture sometimes reports a report
        # as ready when it's really not
        status = lambda: self.suite.request('Report', 'GetStatus', {'reportID': self.id})
        report = lambda: self.suite.request('Report', 'GetReport', {'reportID': self.id})
        self.probe(status, heartbeat, interval)
        response = self.probe(report, heartbeat, interval)
        return Report(response, self)

    def async(self, callback=None, heartbeat=None, interval=1):
        if not self.id:
            self.queue()

        raise NotImplementedError()

    def cancel(self):
        return self.suite.request('Report', 'CancelReport', {'reportID': self.id})


#  TODO: also make this iterable (go through rows)
class Report(object):
    def process(self):
        self.status = self.raw['status']
        self.timing = {
            'queue': float(self.raw['waitSeconds']),
            'execution': float(self.raw['runSeconds']),
        }
        self.report = report = self.raw['report']
        self.metrics = Value.list('metrics', report['metrics'], 'name', 'id')
        self.elements = Value.list('elements', report['elements'], 'name', 'id')
        self.period = report['period']
        segment = report['segment_id']
        if len(segment):
            self.segment = self.query.suite.segments[report['segment_id']]
        else:
            self.segment = None

        self.data = utils.AddressableDict(self.metrics)
        for column in self.data:
            column.value = []

        for row in report['data']:
            for i, value in enumerate(row['counts']):
                if self.metrics[i].type == 'number':
                    value = float(value)
                self.data[i].append(value)

    def to_dataframe(self):
        import pandas as pd
        raise NotImplementedError()
        # return pd.DataFrame()

    def __init__(self, raw, query):
        self.raw = raw
        self.query = query
        self.process()


def sync(queries, heartbeat=None, interval=1):
    for query in queries:
        query.queue()

    return [query.sync(heartbeat, interval) for query in queries]