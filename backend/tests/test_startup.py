import pytest
from postgrest.exceptions import APIError
from config.startup import StartupConfigError, validate_environment
from memory.schema_check import verify_schema


def test_missing_required_config_names_without_values(monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY', '')
    with pytest.raises(StartupConfigError, match='ANTHROPIC_API_KEY'):
        validate_environment()


def test_production_requires_billing_publishing_and_origin(monkeypatch):
    monkeypatch.setenv('ENVIRONMENT', 'production')
    with pytest.raises(StartupConfigError) as error:
        validate_environment()
    for name in ('FRONTEND_ORIGIN', 'PUBLISHING_PROVIDER', 'STRIPE_SECRET_KEY'):
        assert name in str(error.value)


def test_partial_billing_config_fails_at_startup(monkeypatch):
    monkeypatch.setenv('STRIPE_SECRET_KEY', 'test-key')
    with pytest.raises(StartupConfigError, match='STRIPE_WEBHOOK_SECRET'):
        validate_environment()


@pytest.mark.parametrize('origin', ['https://example.com/path', 'https://example.com?x=1', 'garbage'])
def test_invalid_frontend_origin(monkeypatch, origin):
    monkeypatch.setenv('FRONTEND_ORIGIN', origin)
    with pytest.raises(StartupConfigError, match='FRONTEND_ORIGIN'):
        validate_environment()


def test_empty_schema_reads_no_customer_rows(fake_db):
    verify_schema()
    assert not any(fake_db.tables.values())


def test_missing_table_aborts_startup(monkeypatch):
    import memory.schema_check as schema
    def missing(name):
        raise APIError({'code':'PGRST205','message': 'Missing accounts'})
    monkeypatch.setattr(schema.supabase, 'table', missing)
    with pytest.raises(RuntimeError, match='Apply migrations 007'):
        verify_schema()


def test_database_failure_returns_actionable_response_with_cors(client, monkeypatch, auth_headers):
    import routers.account as account
    def unavailable(user_id):
        raise APIError({'code':'PGRST205','message':'Missing accounts'})
    monkeypatch.setattr(account, 'get_account', unavailable)
    response = client.get('/account', headers={**auth_headers('new-user'), 'Origin':'https://contendo-six.vercel.app'})
    assert response.status_code == 503
    assert response.headers['access-control-allow-origin'] == 'https://contendo-six.vercel.app'
    assert 'Please try again' in response.json()['detail']
    assert 'PGRST205' not in response.text
