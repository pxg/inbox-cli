from pathlib import Path

from email_inbox.routing import project_from_input, resolve_project


def test_subject_keyword_acme(tmp_path: Path) -> None:
    (tmp_path / "Projects" / "Acme" / "emails").mkdir(parents=True)
    project, ambiguous = resolve_project(
        tmp_path,
        from_header="Unknown <x@unknown.com>",
        subject="acme - documentation feedback",
    )
    assert project == "Acme"
    assert ambiguous == []


def test_explicit_project(tmp_path: Path) -> None:
    project, ambiguous = resolve_project(
        tmp_path,
        from_header="A <a@b.com>",
        subject="hello",
        explicit="Gamma",
    )
    assert project == "Gamma"
    assert ambiguous == []


def test_explicit_zero(tmp_path: Path) -> None:
    project, ambiguous = resolve_project(
        tmp_path,
        from_header="A <a@b.com>",
        subject="hello",
        explicit="0",
    )
    assert project is None
    assert ambiguous == []


def test_routing_yaml_sender(tmp_path: Path) -> None:
    gmail = tmp_path / "Projects" / "Cursor Gmail"
    gmail.mkdir(parents=True)
    (gmail / "routing.yaml").write_text("senders:\n  bob@client.example.com: Acme\n")
    project, _ = resolve_project(
        tmp_path,
        from_header="Bob Client <bob@client.example.com>",
        subject="hello",
    )
    assert project == "Acme"


def test_project_from_input_by_name(tmp_path: Path) -> None:
    (tmp_path / "Projects" / "Acme" / "emails").mkdir(parents=True)
    assert project_from_input(tmp_path, "Acme") == "Acme"
    assert project_from_input(tmp_path, "0") is None
