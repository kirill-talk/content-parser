"""
HTML content parsing and splitting engine.
Splits unstructured WordPress post HTML into structured fields required by Mach3Blocks:
- item-intro-text
- text-1
- media-2 + media-2-text
- text-2
- instagram
- media-3 + media-3-text
- text-3
"""

import re
import html

class ContentSplitter:
    def __init__(self, raw_html: str, featured_media_url: str = "", post_title: str = ""):
        self.raw_html = raw_html or ""
        self.featured_media_url = featured_media_url or ""
        self.post_title = (post_title or "").strip()
        
    def _clean_block(self, block: str) -> str:
        """Strip WordPress more tags, clean spacing, and remove internal reading recommendations."""
        block = re.sub(r'<!--\s*more\s*-->', '', block)
        block = re.sub(r'<span id="more-\d+"></span>', '', block)
        # Normalize non-breaking spaces
        block = block.replace('&nbsp;', ' ').replace('\xa0', ' ')
        # Strip "Lees ook: ...", "Also read: ...", "Lesen Sie auch: ...", "Lire aussi : ..."
        # recommendations to keep imported content clean from old external internal links
        block = re.sub(
            r'<([a-zA-Z0-9]+)[^>]*>\s*(?:<[^>]+>)*\s*(?:Lees ook|Also read|Lesen Sie auch|À lire aussi|Lire aussi)\s*:?\s*.*?</\1>',
            '',
            block,
            flags=re.DOTALL | re.IGNORECASE
        )
        return block.strip()

    def _normalize_headings(self, html_text: str) -> str:
        """Convert all h1-h6 headings to <h3 class="heading-3 dark">...</h3>."""
        return re.sub(
            r'<h[1-6][^>]*>(.*?)</h[1-6]>',
            r'<h3 class="heading-3 dark">\1</h3>',
            html_text,
            flags=re.DOTALL | re.IGNORECASE
        )

    def _clean_img_url(self, url: str) -> str:
        """Strip WordPress auto-generated thumbnail dimension suffixes like -1067x1600.jpg to get original full-size image."""
        if not url:
            return ""
        # Match pattern like -1200x800.jpg or -1067x1600.jpeg
        cleaned = re.sub(r'-\d{3,4}x\d{3,4}(\.[a-zA-Z]{3,4})$', r'\1', url)
        return cleaned

    def _normalize_figures(self, html_text: str) -> str:
        """
        Convert <figure> tags into clean <p><img...></p> without styles.
        Convert <figcaption> into <p class="heading-6 dark">...</h3>.
        """
        def figure_repl(match):
            content = match.group(1)
            caption_match = re.search(r'<figcaption[^>]*>(.*?)</figcaption>', content, re.DOTALL | re.IGNORECASE)
            caption_html = ""
            if caption_match:
                caption_text = re.sub(r'<[^>]+>', '', caption_match.group(1)).strip()
                if caption_text:
                    caption_html = f'\r\n<p class="heading-6 dark">{caption_text}</p>'
                content = content[:caption_match.start()] + content[caption_match.end():]

            # Extract image src and alt
            src_m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content, re.IGNORECASE)
            alt_m = re.search(r'<img[^>]+alt=["\']([^"\']*)["\']', content, re.IGNORECASE)

            if src_m:
                clean_src = self._clean_img_url(src_m.group(1))
                alt_val = alt_m.group(1) if alt_m else ""
                return f'<p><img src="{clean_src}" alt="{alt_val}"></p>{caption_html}'

            # Fallback if no img tag found
            return f'<p>{content.strip()}</p>{caption_html}'

        return re.sub(r'<figure[^>]*>(.*?)</figure>', figure_repl, html_text, flags=re.DOTALL | re.IGNORECASE)

    def _extract_img_info(self, element_html: str) -> dict:
        """Extract src, alt, caption from an img or figure block, preferring original size."""
        src_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', element_html, re.IGNORECASE)
        alt_match = re.search(r'<img[^>]+alt=["\']([^"\']*)["\']', element_html, re.IGNORECASE)
        caption_match = re.search(r'<figcaption[^>]*>(.*?)</figcaption>', element_html, re.DOTALL | re.IGNORECASE)
        
        raw_src = src_match.group(1) if src_match else ""
        src = self._clean_img_url(raw_src)
        alt = alt_match.group(1) if alt_match else ""
        caption = ""
        if caption_match:
            caption = re.sub(r'<[^>]+>', '', caption_match.group(1)).strip()
        elif alt and not alt.lower().endswith(('.jpg', '.png', '.jpeg', '.webp')):
            caption = alt
            
        return {"src": src, "alt": alt, "caption": caption}

    def _extract_instagram(self, text: str) -> tuple[str, str]:
        """Find Instagram link/embed if present, return (instagram_url, cleaned_text)."""
        insta_match = re.search(r'https?://(?:www\.)?instagram\.com/(?:p|reel)/[a-zA-Z0-9_\-]+/?(?:\?[^\s"\'<>]*)?', text)
        if insta_match:
            insta_url = insta_match.group(0)
            # Remove link or block from text if it was an isolated paragraph
            text = re.sub(r'<p>\s*<a[^>]+href=["\']' + re.escape(insta_url) + r'["\'][^>]*>.*?</a>\s*</p>', '', text)
            text = text.replace(insta_url, '')
            return insta_url, text
        return "", text

    def _clean_tag_attributes(self, html_text: str) -> str:
        """Strip internal WordPress attributes (e.g. data-start, data-end, style) while preserving link href/target and heading styles."""
        def repl(m):
            slash = m.group(1) or ''
            tag = m.group(2).lower()
            full = m.group(0)
            if slash:
                return f'</{tag}>'
            if tag in ('a', 'img'):
                return full
            if 'class="heading-' in full:
                return full
            return f'<{tag}>'
        return re.sub(r'<(/)?([a-zA-Z0-9]+)(?:\s+[^>]*)?>', repl, html_text)

    def split(self) -> dict:
        """Split content into structured slots."""
        # 1. Instagram check
        instagram_url, clean_html = self._extract_instagram(self.raw_html)
        
        # 2. Extract intro text: content before <!--more--> or the first <p>
        intro_text = ""
        body_html = clean_html
        
        if "<!--more-->" in clean_html:
            parts = clean_html.split("<!--more-->", 1)
            raw_intro = self._clean_block(parts[0])
            body_html = parts[1]
            # Strip trailing unclosed or empty <p ...> tags left by more split
            cleaned_intro = re.sub(r'<p(?:\s+[^>]*)?>\s*$', '', raw_intro).strip()
            # Clean attributes from <p ...> tags to <p>
            cleaned_intro = re.sub(r'<(/)?p(?:\s+[^>]*)?>', r'<\1p>', cleaned_intro)
            if cleaned_intro.startswith("<p>"):
                intro_text = cleaned_intro
            else:
                intro_text = f"<p>{cleaned_intro}</p>"
        else:
            first_p = re.search(r'<p(?:\s+[^>]*)?>(.*?)</p>', clean_html, re.DOTALL | re.IGNORECASE)
            if first_p:
                intro_content = first_p.group(1).strip()
                intro_text = f"<p>{intro_content}</p>"
                body_html = clean_html[first_p.end():]
        
        # 3. Tokenize body_html into top-level blocks: <figure>, <img>, <h2>, <h3>, <p>, <ul>, etc.
        # Pattern matches figure blocks, standalone images, or general paragraphs/headings (with attributes like data-start)
        block_pattern = re.compile(
            r'(<figure[^>]*>.*?</figure>|<p[^>]*>\s*<img[^>]+>\s*</p>|<img[^>]+>|<h[1-6][^>]*>.*?</h[1-6]>|<p[^>]*>.*?</p>|<ul[^>]*>.*?</ul>|<ol[^>]*>.*?</ol>|<blockquote[^>]*>.*?</blockquote>)',
            re.DOTALL | re.IGNORECASE
        )
        
        tokens = block_pattern.findall(body_html)
        if not tokens:
            # Fallback if regular html elements weren't caught
            tokens = [b.strip() for b in body_html.split("\n\n") if b.strip()]
            
        elements = []
        for t in tokens:
            cleaned = self._clean_block(t)
            if cleaned:
                elements.append(cleaned)
                
        # 4. Partition elements into slots: text-1, media-2, media-3, text-2 (text-2 now contains all subsequent text)
        media_blocks = []
        text_buckets = [[], []] # bucket 0 -> text-1, bucket 1 -> text-2 (merges former text-2 and text-3)
        current_bucket = 0
        
        for elem in elements:
            # Check if this element is an image/figure
            is_image = elem.startswith('<figure') or '<img' in elem
            # Skip if it is an exact duplicate of the featured media image
            if is_image and self.featured_media_url:
                img_data = self._extract_img_info(elem)
                if img_data['src'] and (img_data['src'] in self.featured_media_url or self.featured_media_url in img_data['src']):
                    continue
            
            if is_image and len(media_blocks) < 2:
                media_blocks.append(self._extract_img_info(elem))
                current_bucket = 1
            else:
                text_buckets[current_bucket].append(elem)
                
        # Format media items into <img> tags as required by new format
        media_2_html = f'<img src="{media_blocks[0]["src"]}" alt="{media_blocks[0]["alt"]}">' if len(media_blocks) > 0 and media_blocks[0]["src"] else ""
        media_2_text = media_blocks[0]["caption"] if len(media_blocks) > 0 else ""
        
        media_3_html = f'<img src="{media_blocks[1]["src"]}" alt="{media_blocks[1]["alt"]}">' if len(media_blocks) > 1 and media_blocks[1]["src"] else ""
        media_3_text = media_blocks[1]["caption"] if len(media_blocks) > 1 else ""
        
        # Normalize headings across text blocks:
        # Convert first h2/heading in text_1 into <h2 class="heading-1 dark">...</h2>
        # Normalize all other headings into <h3 class="heading-3 dark">...</h3>
        bucket_0 = text_buckets[0]
        has_lead_h2 = False
        if bucket_0 and re.match(r'^<h[1-6][^>]*>', bucket_0[0], re.IGNORECASE):
            lead_h2 = bucket_0.pop(0)
            inner_text = re.sub(r'<[^>]+>', '', lead_h2).strip()
            bucket_0.insert(0, f'<h2 class="heading-1 dark">{inner_text}</h2>')
            has_lead_h2 = True

        if has_lead_h2 and len(bucket_0) > 1:
            rest_html = self._normalize_headings("\r\n".join(bucket_0[1:]))
            text_1_html = bucket_0[0] + "\r\n" + rest_html
        elif bucket_0:
            text_1_html = self._normalize_headings("\r\n".join(bucket_0))
        else:
            text_1_html = ""

        text_2_html = self._normalize_headings("\r\n".join(text_buckets[1]))
        
        # Convert any remaining figures inside text_1 and text_2 into clean <p><img...></p> and <p class="heading-6 dark">
        text_1_html = self._normalize_figures(text_1_html)
        text_2_html = self._normalize_figures(text_2_html)

        # Strip remaining internal WordPress attributes (data-start, data-end, etc.)
        text_1_html = self._clean_tag_attributes(text_1_html)
        text_2_html = self._clean_tag_attributes(text_2_html)
        intro_text = self._clean_tag_attributes(intro_text)
        
        # If text_1 ended up empty, distribute from text_2 or intro
        if not text_1_html and text_2_html:
            text_1_html = text_2_html
            text_2_html = ""
            
        return {
            "item-intro-text": intro_text,
            "text-1": text_1_html,
            "media-2": media_2_html,
            "media-2-text": media_2_text,
            "media-3": media_3_html,
            "media-3-text": media_3_text,
            "text-2": text_2_html,
            "instagram": instagram_url,
        }
