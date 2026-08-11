#!/usr/bin/env python3
"""
Upload corrected 더샵 신길센트럴시티 article to WordPress post 2624
Run this locally or on PythonAnywhere
"""

import re
import requests
from requests.auth import HTTPBasicAuth

# Read the generated content
with open('/tmp/generated_apt_article_corrected.txt', 'r', encoding='utf-8') as f:
    content = f.read()

# Extract metadata
title_match = re.search(r'\[TITLE\]:\s*(.*?)\n', content)
focus_kw_match = re.search(r'\[FOCUS_KW\]:\s*(.*?)\n', content)
meta_desc_match = re.search(r'\[META_DESC\]:\s*(.*?)\n', content)
slug_match = re.search(r'\[SLUG\]:\s*(.*?)\n', content)
excerpt_match = re.search(r'\[EXCERPT\]:\s*(.*?)\n', content)

# Extract title, focus keyword, meta description, slug, excerpt
title = title_match.group(1) if title_match else ''
focus_kw = focus_kw_match.group(1) if focus_kw_match else ''
meta_desc = meta_desc_match.group(1) if meta_desc_match else ''
slug = slug_match.group(1) if slug_match else ''
excerpt = excerpt_match.group(1) if excerpt_match else ''

# Extract body (everything after metadata)
body = re.sub(r'^.*?\[EXCERPT\]:.*?\n\n---\n\n', '', content, flags=re.DOTALL)

# Remove markdown code block markers if present
body = re.sub(r'^```html\s*\n', '', body)
body = re.sub(r'\n```\s*$', '', body)

print("=" * 70)
print("더샵 신길센트럴시티 조합원 취소분 WordPress 업로드")
print("=" * 70)
print(f"✅ Title: {title[:60]}...")
print(f"✅ Slug: {slug}")
print(f"✅ Body length: {len(body)} characters")
print(f"✅ Excerpt: {excerpt[:60]}...")
print()

# WordPress credentials
site_url = 'https://www.aptradar.com'
username = 'aptradar@gmail.com'
app_password = 'rfpq jpyz acyu pjqd rfms cxjy'  # Use environment variable in production!
post_id = 2624

# Update WordPress
update_data = {
    'content': body,
    'title': title,
    'slug': slug,
    'excerpt': excerpt,
    'meta': {
        'ap_custom_excerpt': excerpt,
        'rank_math_focus_keyword': focus_kw,
        'rank_math_description': meta_desc,
    }
}

print("📤 Uploading to WordPress post 2624...")
try:
    response = requests.post(
        f'{site_url}/wp-json/wp/v2/posts/{post_id}',
        auth=HTTPBasicAuth(username, app_password),
        json=update_data,
        timeout=30
    )

    if response.status_code in [200, 201]:
        print("✅ Article successfully uploaded!")
        data = response.json()
        print(f"   Post ID: {data.get('id')}")
        print(f"   Title: {data.get('title', {}).get('rendered', '')[:80]}")
        print(f"   Link: {data.get('link')}")
        print()
        print("✨ Your article is now published at WordPress!")
    else:
        print(f"❌ Upload failed with status {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"❌ Error: {e}")
    print("\n💡 If this runs on PythonAnywhere, you may need to use a different endpoint.")

print()
print("=" * 70)
print("After successful upload, run PythonAnywhere update:")
print("cd ~/aptradar && git pull origin claude/aptradar-github-migration-cfds36")
print("=" * 70)
