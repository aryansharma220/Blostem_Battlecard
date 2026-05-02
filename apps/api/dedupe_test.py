from app.pipeline.generator import dedupe_snippets

snippets = [
    {"id": "SN1", "text": "Stripe offers global payment processing with robust fraud protection.", "source_url": "https://stripe.com/pricing", "sections": ["positioning"]},
    {"id": "SN2", "text": "Stripe offers global payment processing with robust fraud protection", "source_url": "https://stripe.com/payments", "sections": ["positioning"]},
    {"id": "SN3", "text": "Stripe pricing is usage-based with volume discounts for enterprise customers.", "source_url": "https://stripe.com/pricing", "sections": ["pricing_posture"]},
    {"id": "SN4", "text": "Stripe pricing is usage-based, with volume discounts for enterprise customers.", "source_url": "https://merchantmaverick.com", "sections": ["pricing_posture"]},
    {"id": "SN5", "text": "Customers report good developer experience and reliable uptime.", "source_url": "https://nerdwallet.com", "sections": ["customer_sentiment"]},
]

print('Before:', len(snippets))
for s in snippets:
    print('-', s['text'])

unique = dedupe_snippets(snippets, similarity_threshold=0.8)
print('\nAfter:', len(unique))
for s in unique:
    print('-', s['text'], 'Citations:', s.get('citations'))
