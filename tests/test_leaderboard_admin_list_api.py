from tests.test_admin_configuration_product import headers, setup


def test_admin_can_list_leaderboards(tmp_path):
    engine, client, (_admin, _member, community), _sessions = setup(tmp_path)
    response = client.get(f"/api/v1/admin/communities/{community}/leaderboards", headers=headers(_admin))
    assert response.status_code == 200
    assert response.json() == []
    engine.dispose()
