"""
Copyright 2019 Splunk, Inc..

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import logging
import time
import requests
import sys
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

TIMEROUT = 500
SPLUNKD_URL = "https://localhost:8089"

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s -' +
                              ' %(levelname)s - %(message)s')
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_events_from_splunk(index="main",
                             start_time="-1h",
                             end_time="now",
                             url=SPLUNKD_URL,
                             user="admin",
                             password="splunk1234"):
    '''
    send a search request to splunk and return the events from the result
    '''
    query = "search index={0}".format(index)
    logger.info("search query = " + str(query))
    events = _collect_events(query, start_time, end_time, url, user, password)
    time.sleep(10)

    if len(events) >= 20:
        logger.info("Integration test passed successfully! ")
        return events
    else:
        raise Exception('Test FAILED')


def _collect_events(query, start_time, end_time, url=SPLUNKD_URL, user="admin", password="splunk1234"):
    '''
    Collect events by running the given search query
    @param: query (search query)
    @param: start_time (search start time)
    @param: end_time (search end time)
    returns events
    '''

    search_url = '{0}/services/search/jobs?output_mode=json'.format(
        url)
    logger.info('requesting: %s', search_url)
    logger.info(query)
    data = {
        'search': query,
        'earliest_time': start_time,
        'latest_time': end_time,
    }

    create_job = _requests_retry_session().post(
        search_url,
        auth=(user, password),
        verify=False, data=data)
    logger.info("Create job request uri " + str(create_job))
    _check_request_status(create_job)

    json_res = create_job.json()
    job_id = json_res['sid']
    logger.info("job id is " + str(job_id))
    events = _wait_for_job_and__get_events(job_id, url, user, password)
    logger.info("Events from search query returned %s events",
                len(events))

    return events


def _wait_for_job_and__get_events(job_id, url="", user="", password=""):
    '''
    Wait for the search job to finish and collect the result events
    @param: job_id
    returns events
    '''
    events = []
    job_url = '{0}/services/search/jobs/{1}?output_mode=json'.format(
        url, str(job_id))
    logger.info('requesting: %s', job_url)

    for _ in range(TIMEROUT):
        res = _requests_retry_session().get(
            job_url,
            auth=(user, password),
            verify=False)
        _check_request_status(res)

        job_res = res.json()
        dispatch_state = job_res['entry'][0]['content']['dispatchState']

        if dispatch_state == 'DONE':
            events = _get_events(job_id, url, user, password)
            break
        if dispatch_state == 'FAILED':
            raise Exception('Search job: {0} failed'.format(job_url))
        time.sleep(1)

    return events


def _get_events(job_id, url=SPLUNKD_URL, user="admin", password="splunk1234"):
    '''
    collect the result events from a search job
    @param: job_id
    returns events
    '''
    event_url = '{0}/services/search/jobs/{1}/events?output_mode=json'.format(
        url, str(job_id))
    logger.info('requesting: %s', event_url)

    event_job = _requests_retry_session().get(
        event_url, auth=(user, password),
        verify=False)
    _check_request_status(event_job)

    event_job_json = event_job.json()
    events = event_job_json['results']
    logger.info("Events from get_events method returned %s events",
                len(events))

    return events


def _check_request_status(req_obj):
    '''
    check if a request is successful
    @param: req_obj
    returns True/False
    '''
    if not req_obj.ok:
        raise Exception('status code: {0} \n details: {1}'.format(
            str(req_obj.status_code), req_obj.text))


def _requests_retry_session(
        retries=10,
        backoff_factor=0.1,
        status_forcelist=(500, 502, 504)):
    '''
    create a retry session for HTTP/HTTPS requests
    @param: retries (num of retry time)
    @param: backoff_factor
    @param: status_forcelist (list of error status code to trigger retry)
    @param: session
    returns: session
    '''
    session = requests.Session()
    retry = Retry(
        total=int(retries),
        backoff_factor=backoff_factor,
        method_whitelist=frozenset(['GET', 'POST']),
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    return session


if __name__ == '__main__':
    check_events_from_splunk()
