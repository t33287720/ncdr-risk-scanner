import os
import shutil

ACTIVE_STATUSES = ('pending', 'running')


def delete_job_files(job_id, jobs_dir, results_dir, status):
    """刪除工作 JSON 與結果資料夾。

    回傳 (ok, error)；工作不存在回 (False, 'not_found')，執行中回 (False, 'active')。
    """
    job_file = os.path.join(jobs_dir, f'{job_id}.json')
    if not job_id or not os.path.exists(job_file):
        return False, 'not_found'
    if status in ACTIVE_STATUSES:
        return False, 'active'
    os.remove(job_file)
    shutil.rmtree(os.path.join(results_dir, job_id), ignore_errors=True)
    return True, None
