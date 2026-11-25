import pytest

from cuad_ai.live import admin, tenants


def test_the_admin_commands_set_up_a_client_end_to_end(live_db):
    lines = []
    with live_db() as conn:
        def run(*argv):
            lines.clear()
            admin.run(conn, list(argv), lines.append)
            return "\n".join(lines)

        assert "saved" in run("add-client", "acme", "Acme Corp", "--retention", "14", "--daily-cap", "5")
        assert tenants.get_tenant(conn, "acme")["retention_days"] == 14
        run("add-user", "acme", "Ann@Acme.com")
        assert tenants.tenant_for_email(conn, "ann@acme.com") == "acme"
        assert "ann@acme.com" in run("list")

        run("key", "acme")
        key = next(line for line in lines if line.startswith("lk_"))
        assert tenants.tenant_for_key(conn, key) == "acme"

        assert run("audit", "acme") == "no entries"
        assert "removed" == run("remove-user", "ann@acme.com")
        assert "not on the list" in run("remove-user", "ann@acme.com")
        assert run("purge") == "deleted 0 expired upload(s)"


def test_mistakes_give_a_clear_message_not_a_traceback(live_db):
    with live_db() as conn:
        for argv in (["add-client", "Bad Id", "x"], ["add-user", "nobody", "a@b.com"], ["key", "nobody"]):
            with pytest.raises(SystemExit, match="error:"):
                admin.run(conn, argv, lambda _: None)
