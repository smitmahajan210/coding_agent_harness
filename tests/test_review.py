from review import changed_lines, highlighted_code


def test_highlights_multiple_separate_fixes_without_marking_unchanged_context():
    before = 'def first():\n    return 1\n\ndef second():\n    return 2\n'
    after = 'def first():\n    return 10\n\ndef second():\n    return 20\n'
    changes = changed_lines(before, after)
    assert changes == {'before': {2, 5}, 'after': {2, 5}, 'blocks': 2}
    rendered = highlighted_code(after, changes['after'], side='after')
    assert rendered.count('class="review-line changed-after"') == 2
    assert 'Added or changed line 2' in rendered
    assert 'Added or changed line 5' in rendered
    assert 'Unchanged line 4' in rendered
    assert 'def first():' in rendered and 'def second():' in rendered


def test_insertions_and_deletions_keep_correct_line_numbers():
    changes = changed_lines('a\nb\nc\n', 'new\na\nc\n')
    assert changes['before'] == {2}
    assert changes['after'] == {1}
    assert changed_lines('', 'a\nb\n')['after'] == {1, 2}
    assert changed_lines('a\nb\n', '')['before'] == {1, 2}
    assert changed_lines('unchanged\n', 'unchanged\n')['blocks'] == 0


def test_code_is_escaped_including_script_and_style_tags():
    source = '<script>alert("x")</script>\n</code><img src=x onerror=alert(1)>\n<style>body{display:none}</style>'
    rendered = highlighted_code(source, {1, 2, 3}, side='after')
    assert '<script>' not in rendered
    assert '<img ' not in rendered
    assert '&lt;script&gt;' in rendered
    assert '&lt;style&gt;body{display:none}&lt;/style&gt;' in rendered
