import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
from job_utils import delete_job_files


def _setup(tmp, job_id):
    jobs, results = os.path.join(tmp, 'jobs'), os.path.join(tmp, 'results')
    os.makedirs(os.path.join(results, job_id))
    os.makedirs(jobs)
    with open(os.path.join(jobs, f'{job_id}.json'), 'w') as f:
        json.dump({'id': job_id}, f)
    open(os.path.join(results, job_id, 'results.csv'), 'w').close()
    return jobs, results


def test_delete_done():
    with tempfile.TemporaryDirectory() as tmp:
        jobs, results = _setup(tmp, 'abc')
        assert delete_job_files('abc', jobs, results, 'done') == (True, None)
        assert not os.path.exists(os.path.join(jobs, 'abc.json'))
        assert not os.path.exists(os.path.join(results, 'abc'))


def test_refuse_active():
    with tempfile.TemporaryDirectory() as tmp:
        jobs, results = _setup(tmp, 'abc')
        assert delete_job_files('abc', jobs, results, 'running') == (False, 'active')
        assert os.path.exists(os.path.join(jobs, 'abc.json'))


def test_not_found():
    with tempfile.TemporaryDirectory() as tmp:
        jobs, results = _setup(tmp, 'abc')
        assert delete_job_files('zzz', jobs, results, 'done') == (False, 'not_found')


if __name__ == '__main__':
    test_delete_done(); test_refuse_active(); test_not_found()
    print('ok')
