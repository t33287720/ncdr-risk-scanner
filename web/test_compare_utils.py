from compare_utils import diff_jobs


def row(name, lon, lat, risk, hazard='第一級'):
    return {'地點名稱': name, '經度': lon, '緯度': lat, '淹水風險': risk, '淹水危害度': hazard}


def test_diff():
    old = [row('A', '121.5', '25.0', '第二級'), row('B', '121.6', '25.1', '第四級'),
           row('C', '121.7', '25.2', '第三級'), row('D', '121.8', '25.3', '第一級')]
    new = [row('A', '121.5', '25.0', '第三級'), row('B', '121.6', '25.1', '第二級'),
           row('C', '121.7', '25.2', '第三級'), row('E', '121.9', '25.4', '第一級')]
    d = diff_jobs(old, new)
    assert d['changes'] == {0: 'up', 1: 'down', 2: 'same', 3: 'new'}
    assert d['removed'] == ['D']
    assert d['counts'] == {'up': 1, 'down': 1, 'same': 1, 'new': 1, 'removed': 1}


def test_same_name_moved_is_new():
    d = diff_jobs([row('A', '121.5', '25.0', '第二級')], [row('A', '121.9', '25.0', '第二級')])
    assert d['changes'] == {0: 'new'} and d['removed'] == ['A']


def test_missing_data_ignored():
    d = diff_jobs([row('A', '1', '2', '無資料')], [row('A', '1', '2', '第五級')])
    assert d['changes'] == {0: 'same'}


if __name__ == '__main__':
    test_diff(); test_same_name_moved_is_new(); test_missing_data_ignored()
    print('ok')
