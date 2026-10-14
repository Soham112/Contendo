from memory.hierarchy_store import upsert_topic_node, get_topic_node, upsert_source_node, get_source_node


def test_hierarchy_upserts_are_scoped_to_user(fake_db):
    for user_id in ('alice', 'bob'):
        upsert_topic_node('same-topic', user_id, user_id + ' topic', '', ['work'], [])
        upsert_source_node('same-source', user_id, user_id + ' source', 'personal_note',
                           '2026-10-14T00:00:00Z', ['work'], 1, 'same-topic', user_id + ' summary')
    assert get_topic_node('same-topic', 'alice')['topic_label'] == 'alice topic'
    assert get_topic_node('same-topic', 'bob')['topic_label'] == 'bob topic'
    assert get_source_node('same-source', 'alice')['source_summary'] == 'alice summary'
    assert get_source_node('same-source', 'bob')['source_summary'] == 'bob summary'
    upsert_topic_node('same-topic', 'alice', 'updated', '', ['work'], ['same-source'])
    assert len(fake_db.tables['topic_nodes']) == 2
    assert get_topic_node('same-topic', 'bob')['topic_label'] == 'bob topic'
