<!-- version: 1.0 -->
Draft a complete business-category template for an ad-testing product. The template drives (a) the questions a business owner answers about their business and (b) the traits of simulated customers.

Category name: {{name}}
Suggested code: {{code}}
Parent category: {{parent_code}}
Extra hints from the admin: {{hints}}

Requirements:
- 10-16 questions. Always include: business_name (text, required), what_you_sell (text, required), price_level (select budget|mid|premium, required, feeds_trait price_level), a `sliders` question whose options are the taste/preference dimensions (feeds_trait taste), customer_mix (select of the customer mix names, feeds_trait familiarity), customer_languages (multiselect th|en|my|zh|ja|ko|es, feeds_trait language_group), followers (number, required, feeds_trait brand_relationship), review_count, rating, months_in_business (numbers, feeds_trait brand_relationship).
- Use snake_case keys and option codes. `options` must be an empty array for text/number/boolean questions.
- 3-4 taste dimensions relevant to the category.
- 3-5 customer mixes; each mix's four shares add up to 1.
- Blockers use only the codes price, shipping, size, trust, relevance with weights adding up to 1.
- Typical goals from: sales, messages, traffic, awareness, engagement.
- benchmark_adjustments are multipliers (0.5-2.5) on market benchmarks for metrics among: ctr, cvr, message_rate, engagement_rate, save_rate, stop_rate.
- Restrictions: short notes on regulated claims or goods for this category.
