from app import create_app, db
from config.settings import TestingConfig
from app.tests.tests_api import _seed_test_data

app = create_app(TestingConfig)
with app.app_context():
    db.create_all()
    _seed_test_data(app)
    c = app.test_client()

    r1 = c.post('/api/auth/login', json={'email': 'testdoc@neurotrace.ai', 'password': 'Test123!'})
    print('login', r1.status_code, r1.get_json())

    d = r1.get_json().get('data', {})
    token = d.get('access_token')
    rt = d.get('refresh_token')
    print('access present', bool(token), 'refresh present', bool(rt))

    r2 = c.get('/api/fusion/dashboard/PT-TEST', headers={'Authorization': 'Bearer {}'.format(token)})
    print('fusion', r2.status_code, r2.get_json())

    r3 = c.post('/api/auth/refresh', headers={'Authorization': 'Bearer {}'.format(rt)})
    print('refresh', r3.status_code, r3.get_json())

    if r3.status_code == 200:
        new = r3.get_json().get('data', {})
        newat = new.get('access_token')
        r4 = c.get('/api/fusion/dashboard/PT-TEST', headers={'Authorization': 'Bearer {}'.format(newat)})
        print('fusion2', r4.status_code, r4.get_json())
