"""Dynamic Feature Atlas API tests (Phase III: "make it dynamic").

Covers the live portfolio endpoints: authentication, summary integrity
(1,080 portfolio / 36 domains), filtering by domain/status/priority, search,
pagination, single-feature lookup with 404, and the admin-gated validator.
"""
COORD = "coordinator@example.dev"
VOL = "volunteer@example.dev"
ADMIN = "ngo-admin@example.dev"


class TestAtlasAccess:
    def test_unauthenticated_rejected(self, client):
        for path in ("/api/v1/features", "/api/v1/features/summary",
                     "/api/v1/features/domains"):
            assert client.get(path).status_code == 401

    def test_authenticated_list_ok(self, client):
        h = client.login(COORD)
        r = client.get("/api/v1/features?limit=5", headers=h)
        assert r.status_code == 200
        body = r.json()
        assert body["returned"] == len(body["features"]) == 5
        assert body["total"] >= 1080
        f = body["features"][0]
        for field in ("feature_id", "domain_id", "name", "description",
                      "current_status", "priority"):
            assert field in f


class TestAtlasSummary:
    def test_summary_portfolio_integrity(self, client):
        h = client.login(COORD)
        s = client.get("/api/v1/features/summary", headers=h).json()
        assert s["portfolio"] == 1080
        assert s["domains"] == 36
        assert s["min_per_domain"] >= 30
        assert sum(s["by_domain"].values()) == s["portfolio"]
        # every catalogued record is accounted for in the status counts
        assert sum(s["by_status"].values()) == s["total_records"]
        assert s["total_records"] > s["portfolio"]  # rejected excluded

    def test_domain_catalog_rollup(self, client):
        h = client.login(COORD)
        r = client.get("/api/v1/features/domains", headers=h)
        domains = r.json()["domains"]
        assert len(domains) == 36
        assert sum(d["features"] for d in domains) == 1080
        assert all(d["avg_priority_score"] > 0 for d in domains)
        ids = [d["domain_id"] for d in domains]
        assert ids == sorted(ids)  # deterministic ordering


class TestAtlasFiltering:
    def test_domain_filter(self, client):
        h = client.login(COORD)
        body = client.get("/api/v1/features?domain=inv", headers=h).json()
        assert body["total"] >= 30
        assert all(f["domain_id"] == "INV" for f in body["features"])

    def test_status_filter_excludes_rejected_from_portfolio(self, client):
        h = client.login(COORD)
        body = client.get("/api/v1/features?status=REJECTED", headers=h).json()
        # REJECTED records are never part of the queryable portfolio
        assert body["total"] == 0
        body = client.get("/api/v1/features?status=EXISTING_VERIFIED", headers=h).json()
        assert 200 <= body["total"] <= 300
        assert all(f["current_status"] == "EXISTING_VERIFIED"
                   for f in body["features"])

    def test_priority_filter(self, client):
        h = client.login(COORD)
        body = client.get("/api/v1/features?priority=P0", headers=h).json()
        assert body["total"] > 0
        assert all(f["priority"] == "P0" for f in body["features"])

    def test_search_matches_name_or_id(self, client):
        h = client.login(COORD)
        body = client.get("/api/v1/features?search=expiry", headers=h).json()
        assert body["total"] > 0
        needle = "expiry"
        assert all(
            needle in f["name"].lower() or needle in f["description"].lower()
            or needle in f["feature_id"].lower() for f in body["features"])

    def test_combined_filters(self, client):
        h = client.login(COORD)
        body = client.get(
            "/api/v1/features?domain=VOL&status=IMPLEMENTED_TESTED",
            headers=h).json()
        assert body["total"] >= 1
        assert all(f["domain_id"] == "VOL"
                   and f["current_status"] == "IMPLEMENTED_TESTED"
                   for f in body["features"])


class TestAtlasPagination:
    def test_offset_walk_covers_all(self, client):
        h = client.login(COORD)
        page1 = client.get("/api/v1/features?limit=50&offset=0", headers=h).json()
        assert page1["returned"] == 50
        page2 = client.get("/api/v1/features?limit=50&offset=50", headers=h).json()
        ids1 = {f["feature_id"] for f in page1["features"]}
        ids2 = {f["feature_id"] for f in page2["features"]}
        assert not (ids1 & ids2)  # no overlap between pages

    def test_offset_past_end_returns_empty(self, client):
        h = client.login(COORD)
        body = client.get("/api/v1/features?limit=50&offset=999999",
                          headers=h).json()
        assert body["returned"] == 0 and body["features"] == []
        assert body["total"] >= 1080  # total still the filtered count


class TestAtlasSingleFeature:
    def test_get_existing_feature(self, client):
        h = client.login(COORD)
        listing = client.get("/api/v1/features?limit=1", headers=h).json()
        fid = listing["features"][0]["feature_id"]
        r = client.get(f"/api/v1/features/{fid}", headers=h)
        assert r.status_code == 200
        assert r.json()["feature_id"] == fid
        # full 33-field schema record, not a projection
        rec = r.json()
        for field in ("problem", "primary_actor", "user_outcome",
                      "acceptance_criteria", "dependencies", "failure_modes"):
            assert field in rec

    def test_get_unknown_feature_404(self, client):
        h = client.login(COORD)
        assert client.get("/api/v1/features/NOSUCH-999", headers=h).status_code == 404


class TestAtlasValidator:
    def test_validate_forbidden_for_coordinator(self, client):
        h = client.login(COORD)
        r = client.post("/api/v1/features/validate", headers=h)
        assert r.status_code == 403

    def test_validate_forbidden_for_volunteer(self, client):
        h = client.login(VOL)
        assert client.post("/api/v1/features/validate",
                           headers=h).status_code == 403

    def test_validate_ok_for_admin(self, client):
        h = client.login(ADMIN)
        r = client.post("/api/v1/features/validate", headers=h)
        assert r.status_code == 200
        body = r.json()
        assert body["valid"] is True and body["exit_code"] == 0
        assert "ATLAS VALID" in body["output"]
