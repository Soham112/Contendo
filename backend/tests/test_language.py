"""The language check at ingestion (utils/language.py, ingest_content): every
input type is identified, a source confidently in a language the embedder can't
search is refused before any model call or write, short text is accepted as
undetermined, and the result is stored on the source as `lang`."""
import pytest

from tests.extraction_fixtures import jina

USER = "user-a"

SPANISH = ("La semana pasada reconstruimos todo el proceso de registro de la aplicación. La lección más "
           "importante fue que los usuarios no leen las ayudas: hacen clic en el primer botón que ven y "
           "siguen adelante. Por eso quitamos casi todas las explicaciones y pusimos los pasos clave "
           "directamente en el texto de los botones. Las conversiones subieron y las preguntas al soporte "
           "bajaron de forma clara durante el mes siguiente.")
ENGLISH = ("Last week we rebuilt the whole signup flow. The biggest lesson was that users don't read "
           "tooltips: they click the first button they see and move on. So we removed most of the "
           "explanations and put the key steps straight into the button labels. Conversions went up and "
           "support questions dropped clearly over the following month. Next quarter we want to try the same "
           "approach on the billing settings page.")


@pytest.fixture
def ingestion(claude):
    claude.respond_with(lambda kwargs: "[]")


@pytest.fixture
def headers(client, production, auth_headers):
    return auth_headers(USER)


def _note(client, headers, text):
    return client.post("/ingest", headers=headers, json={"source_type": "note", "content": text})


def test_a_non_english_article_is_refused_before_any_model_call_or_write(client, headers, fake_db, claude,
                                                                         monkeypatch):
    import extractors.url as url_extractor
    page = jina("jina_wikipedia_rag.json")
    page["data"] |= {"title": "Cómo reconstruimos el registro", "content": f"# Registro\n\n{SPANISH}"}
    monkeypatch.setattr(url_extractor, "fetch", lambda url: page)
    resp = client.post("/scrape-and-ingest", headers=headers, json={"url": "https://example.es/registro"})
    assert resp.status_code == 422
    assert resp.json()["detail"] == "This looks like Spanish. Contendo can only learn from English for now."
    assert claude.calls == []
    assert fake_db.tables["sources"] == [] and not fake_db.tables.get("embeddings")


def test_a_non_english_file_and_note_are_refused(client, headers, fake_db, claude):
    upload = client.post("/ingest-file", headers=headers,
                         files={"file": ("notas.md", f"# Notas\n\n{SPANISH}".encode(), "text/markdown")})
    assert upload.status_code == 422 and "Spanish" in upload.json()["detail"]
    assert _note(client, headers, SPANISH).status_code == 422
    assert claude.calls == [] and fake_db.tables["sources"] == []


def test_english_is_stored_with_its_language(client, headers, fake_db, ingestion):
    assert _note(client, headers, ENGLISH).status_code == 200
    [row] = fake_db.tables["sources"]
    assert row["lang"] == "en"


@pytest.mark.parametrize("text", ["Meeting w/ Raj re pricing", "Reunión con Raj sobre precios mañana",
                                  "RAG eval: recall@5 0.82, MRR 0.61"])
def test_short_text_is_accepted_as_undetermined(client, headers, fake_db, ingestion, text):
    assert _note(client, headers, text).status_code == 200
    [row] = fake_db.tables["sources"]
    assert row["lang"] is None


def test_code_heavy_english_is_not_mistaken_for_another_language():
    """Before code was removed by syntax, text like this read as Latin or Dutch."""
    from utils.language import detect
    text = ("### retrieval_agent.py: `infer_seniority_level()`\n\n| **Signature** | `infer_seniority_level(text)` |\n"
            "**Pipeline position:** `predictability_audit → word_count_enforcer → fact_checker → finalise`. "
            "```python\nfor row in rows:\n    upsert_chunks(row.id, row.text)\n```\n") * 3 + ENGLISH
    assert detect(text).lang == "en"


def test_symbols_and_capitals_do_not_decide_the_language():
    """The real Despacito track: Spanish lyrics in capitals between ♪ read as Gujarati."""
    from utils.language import detect
    assert detect(" ".join(f"♪ {line} ♪" for line in SPANISH.upper().split(". "))).lang == "es"


def test_the_text_decides_and_the_provider_code_is_used_only_when_it_cannot():
    from utils.language import resolve
    assert resolve(SPANISH, "en") == "es"          # Supadata said en for Spanish
    assert resolve(ENGLISH, "ar") == "en"
    assert resolve("Hola a todos", "es-419") == "es"
    assert resolve("Hola a todos", None) is None


def test_other_scripts_are_identified_at_the_same_floor():
    """The floor is in bytes, so a Chinese or Arabic note of the same substance is judged too."""
    from utils.language import detect
    chinese = ("这个周末我重新设计了我们应用的注册流程。最大的教训是用户根本不读提示信息，他们只会点击看到的第一个按钮"
               "然后继续前进。我们因此删除了大部分提示，把关键步骤直接放进按钮文字里，转化率提高了不少，"
               "客服问题也明显减少了。")
    arabic = ("قضيت عطلة نهاية الأسبوع في إعادة بناء تدفق التسجيل في تطبيقنا. كان الدرس الأكبر أن المستخدمين "
              "لا يقرؤون التلميحات، بل ينقرون على أول زر يرونه ويمضون قدما. لذلك حذفنا معظم الشروح ووضعنا الخطوات "
              "الأساسية في نص الأزرار مباشرة.")
    assert (detect(chinese).lang, detect(arabic).lang) == ("zh", "ar")
