from datetime import timedelta

from tests.support.account_lifecycle import (
    ACCOUNT_LIFECYCLE_TEST_KEY_ID,
    DEFAULT_ACCOUNT_LIFECYCLE_TIME,
    DisposableAccountIdentityBuilder,
    InMemoryAccountLifecycleMailbox,
)


def test_account_lifecycle_support_is_isolated_for_first_test(
    account_lifecycle_clock,
    account_lifecycle_keyring,
    disposable_account_identity_builder,
    in_memory_account_lifecycle_mailbox,
):
    assert disposable_account_identity_builder.count == 0
    assert in_memory_account_lifecycle_mailbox.messages == ()

    identity = disposable_account_identity_builder.build(locale="en")
    message = in_memory_account_lifecycle_mailbox.deliver(
        recipient=identity.email,
        purpose="EMAIL_VERIFICATION",
        locale=identity.locale,
        opaque_test_token=identity.opaque_test_token,
    )
    account_lifecycle_clock.advance(hours=1)
    account_lifecycle_keyring["test-only-override"] = b"local"

    assert disposable_account_identity_builder.count == 1
    assert in_memory_account_lifecycle_mailbox.messages == (message,)
    assert account_lifecycle_clock.now() == DEFAULT_ACCOUNT_LIFECYCLE_TIME + timedelta(hours=1)


def test_account_lifecycle_support_is_isolated_for_second_test(
    account_lifecycle_clock,
    account_lifecycle_keyring,
    disposable_account_identity_builder,
    in_memory_account_lifecycle_mailbox,
):
    assert disposable_account_identity_builder.count == 0
    assert in_memory_account_lifecycle_mailbox.messages == ()
    assert not hasattr(in_memory_account_lifecycle_mailbox, "write")
    assert not hasattr(in_memory_account_lifecycle_mailbox, "send_http")
    assert account_lifecycle_clock.now() == DEFAULT_ACCOUNT_LIFECYCLE_TIME
    assert account_lifecycle_keyring == {
        ACCOUNT_LIFECYCLE_TEST_KEY_ID: bytes(range(32)),
    }

    identity = disposable_account_identity_builder.build(locale="ar")
    independent = DisposableAccountIdentityBuilder(seed="independent-builder").build(
        locale="ar"
    )
    standalone_mailbox = InMemoryAccountLifecycleMailbox()

    assert identity.email.endswith("@example.test")
    assert identity.opaque_test_token != independent.opaque_test_token
    assert standalone_mailbox.messages == ()
