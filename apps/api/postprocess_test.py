from app.pipeline.generator import _fallback_json, post_process_payload

# Create a fallback payload with verbose repeating claims to test compression
snippets = [
]
sources = [
    {"url": "https://stripe.com/pricing", "title": "Pricing & Fees"},
    {"url": "https://stripe.com/", "title": "Stripe"},
]

fb = _fallback_json("Stripe", [
    {"id":"1","text":"Expand to new markets quickly and globally.","source_url":"https://stripe.com/pricing","sections":["positioning"]},
    {"id":"2","text":"Expand to new markets quickly and globally.","source_url":"https://stripe.com/","sections":["positioning"]},
    {"id":"3","text":"Usage-based pricing with volume discounts for enterprise customers.","source_url":"https://stripe.com/pricing","sections":["pricing_posture"]},
    {"id":"4","text":"Usage-based pricing with volume discounts for enterprise customers.","source_url":"https://merchantmaverick.com","sections":["pricing_posture"]},
    {"id":"5","text":"Customers praise developer experience and APIs.","source_url":"https://nerdwallet.com","sections":["customer_sentiment"]},
], sources)

print('Before sections:')
for k,v in fb['sections'].items():
    print(k, len(v))

pp = post_process_payload(fb, max_bullets=3, max_words_per_bullet=8)

print('\nAfter sections:')
for k,v in pp['sections'].items():
    print(k, len(v))
    for it in v:
        print('-', it.get('claim'), 'Cits:', it.get('citations'))
