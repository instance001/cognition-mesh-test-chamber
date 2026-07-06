from cm_test_chamber.sandbox.patch_guard import analyze_patch


def test_patch_guard_detects_invented_paths():
    analysis = analyze_patch(
        "--- a/src/missing.py\n+++ b/src/missing.py\n@@\n+print('hi')\n",
        allowed_files={"src/app.py"},
        manifest={"src/app.py"},
        allow_new_files=False,
    )
    assert analysis.invented_paths == ["src/missing.py"]
    assert analysis.broad_patch is True


def test_patch_guard_accepts_single_allowed_file():
    analysis = analyze_patch(
        "--- a/src/app.py\n+++ b/src/app.py\n@@\n-    return \"Hello\"\n+    return \"Hello there\"\n",
        allowed_files={"src/app.py"},
        manifest={"src/app.py"},
        allow_new_files=False,
    )
    assert analysis.invented_paths == []
    assert analysis.broad_patch is False
