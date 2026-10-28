import citedesk


def test_package_imports_and_has_version() -> None:
    assert citedesk.__version__
