from cm_test_chamber.model_catalog import format_catalog, load_catalog


def test_assistant_catalog_loads(repo_root):
    catalog = load_catalog(repo_root / "configs" / "catalogs" / "assistant_models.json")
    assert catalog.role == "assistant"
    assert catalog.models
    assert catalog.models[0].file_path.startswith("assistant_models/")
    assert catalog.models[0].temperature == 0.2
    assert catalog.models[1].temperature == 0.0


def test_model_under_test_catalog_formats(repo_root):
    catalog = load_catalog(repo_root / "configs" / "catalogs" / "models_under_test.json")
    rendered = format_catalog(catalog)
    assert "Role: model_under_test" in rendered
    assert "model_under_test/" in rendered
