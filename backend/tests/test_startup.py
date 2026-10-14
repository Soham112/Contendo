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


def test_zernio_requires_its_secrets_without_disclosing_configured_values(monkeypatch):
    monkeypatch.setenv('PUBLISHING_PROVIDER', 'zernio')
    monkeypatch.setenv('FRONTEND_ORIGIN', 'https://www.contendoai.com')
    monkeypatch.setenv('ZERNIO_API_KEY', 'private-key-never-print')
    with pytest.raises(StartupConfigError) as error:
        validate_environment()
    assert 'ZERNIO_WEBHOOK_SECRET' in str(error.value)
    assert 'private-key-never-print' not in str(error.value)


def test_production_rejects_insecure_frontend_origin(monkeypatch):
    monkeypatch.setenv('ENVIRONMENT', 'production')
    monkeypatch.setenv('FRONTEND_ORIGIN', 'http://www.contendoai.com')
    monkeypatch.setenv('PUBLISHING_PROVIDER', 'zernio')
    for key in ('STRIPE_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET', 'STRIPE_PRICE_ID_PRO',
                'ZERNIO_API_KEY', 'ZERNIO_WEBHOOK_SECRET'):
        monkeypatch.setenv(key, 'test-value')
    with pytest.raises(StartupConfigError, match='FRONTEND_ORIGIN'):
        validate_environment()


def test_valid_production_config(monkeypatch):
    monkeypatch.setenv('ENVIRONMENT', 'production')
    monkeypatch.setenv('FRONTEND_ORIGIN', 'https://www.contendoai.com')
    monkeypatch.setenv('PUBLISHING_PROVIDER', 'zernio')
    for key in ('STRIPE_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET', 'STRIPE_PRICE_ID_PRO',
                'ZERNIO_API_KEY', 'ZERNIO_WEBHOOK_SECRET'):
        monkeypatch.setenv(key, 'test-value')
    validate_environment()


@pytest.mark.parametrize('trial', ['seven', '1.5'])
def test_invalid_stripe_trial_aborts_startup(monkeypatch, trial):
    monkeypatch.setenv('FRONTEND_ORIGIN', 'https://www.contendoai.com')
    for key in ('STRIPE_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET', 'STRIPE_PRICE_ID_PRO'):
        monkeypatch.setenv(key, 'test-value')
    monkeypatch.setenv('STRIPE_TRIAL_DAYS', trial)
    with pytest.raises(StartupConfigError, match='STRIPE_TRIAL_DAYS'):
        validate_environment()


def test_environment_must_be_explicit_so_production_checks_cannot_be_skipped(monkeypatch):
    monkeypatch.delenv('ENVIRONMENT', raising=False)
    with pytest.raises(StartupConfigError, match='ENVIRONMENT'):
        validate_environment()


def _production_without_stripe(monkeypatch):
    monkeypatch.setenv('ENVIRONMENT', 'production')
    monkeypatch.setenv('FRONTEND_ORIGIN', 'https://www.contendoai.com')
    monkeypatch.setenv('PUBLISHING_PROVIDER', 'zernio')
    monkeypatch.setenv('ZERNIO_API_KEY', 'zernio-key')
    monkeypatch.setenv('ZERNIO_WEBHOOK_SECRET', 'zernio-secret')


def test_production_starts_without_stripe_only_when_billing_is_turned_off(monkeypatch):
    _production_without_stripe(monkeypatch)
    with pytest.raises(StartupConfigError, match='STRIPE_SECRET_KEY'):
        validate_environment()
    monkeypatch.setenv('BILLING_DISABLED', '1')
    validate_environment()


@pytest.mark.parametrize('value', ['true', 'yes', '0', ' 1x'])
def test_billing_disabled_must_be_exactly_1(monkeypatch, value):
    _production_without_stripe(monkeypatch)
    monkeypatch.setenv('BILLING_DISABLED', value)
    with pytest.raises(StartupConfigError, match='STRIPE_SECRET_KEY'):
        validate_environment()


def test_billing_disabled_with_stripe_settings_is_refused(monkeypatch):
    _production_without_stripe(monkeypatch)
    monkeypatch.setenv('BILLING_DISABLED', '1')
    monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk_live_x')
    with pytest.raises(StartupConfigError, match='remove one'):
        validate_environment()


def test_turning_billing_off_still_requires_publishing(monkeypatch):
    monkeypatch.setenv('ENVIRONMENT', 'production')
    monkeypatch.setenv('FRONTEND_ORIGIN', 'https://www.contendoai.com')
    monkeypatch.setenv('BILLING_DISABLED', '1')
    with pytest.raises(StartupConfigError, match='PUBLISHING_PROVIDER'):
        validate_environment()
