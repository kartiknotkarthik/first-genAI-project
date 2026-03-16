/**
 * Pure UI logic helpers for the Phase 5 page.
 * These functions are unit-tested with Jest.
 */

/**
 * Build a normalized request payload from the preference form values.
 *
 * @param {Object} fields - Raw field values as strings.
 * @returns {Object} Payload with freeText and structured preferences.
 */
export function buildRequestPayload(fields) {
  const {
    freeText = "",
    city = "",
    cuisine = "",
    minRating = "",
    maxPrice = "",
    limit = "10",
  } = fields;

  const trimmedFreeText = freeText.trim();

  // Create a combined user message for the LLM to parse
  const parts = [];
  if (trimmedFreeText) parts.push(trimmedFreeText);
  if (city) parts.push(`in ${city}`);
  if (cuisine) parts.push(`serving ${cuisine}`);
  if (minRating) parts.push(`at least ${minRating} stars`);
  if (maxPrice) parts.push(`budget level ${maxPrice}`);

  const payload = {
    user_message: parts.join(", ") || "Recommend restaurants",
    limit: Number(limit) || 10,
    preferences: {
      city: city.trim() || null,
      cuisine: cuisine.trim() || null,
      min_rating: minRating ? Number(minRating) : null,
      max_price_range: maxPrice ? Number(maxPrice) : null,
    },
  };

  return payload;
}

/**
 * Validate that the form has enough information to send a request.
 * We require at least one of: free text, city, or cuisine.
 *
 * @param {Object} fields
 * @returns {{ valid: boolean, message: string | null }}
 */
export function validateFields(fields) {
  const hasFreeText = fields.freeText && fields.freeText.trim().length > 0;
  const hasCity = fields.city && fields.city.trim().length > 0;
  const hasCuisine = fields.cuisine && fields.cuisine.trim().length > 0;

  if (!hasFreeText && !hasCity && !hasCuisine) {
    return {
      valid: false,
      message:
        "Please describe what you’re looking for, or provide at least a city or cuisine.",
    };
  }

  if (fields.minRating && isNaN(Number(fields.minRating))) {
    return { valid: false, message: "Minimum rating must be a number." };
  }

  if (fields.maxPrice && isNaN(Number(fields.maxPrice))) {
    return { valid: false, message: "Budget must be a valid option." };
  }

  return { valid: true, message: null };
}

/**
 * Transform backend restaurant objects into display-friendly cards.
 *
 * @param {Array<Object>} restaurants
 * @returns {Array<Object>} Display cards
 */
export function mapRestaurantsToCards(restaurants) {
  return (restaurants || []).map((r) => {
    const name = r.name || "Unknown";
    const city = r.city || "";
    const location = r.location || r.locality || "";
    const cuisine = r.cuisine || r.cuisines || "";
    
    // Parse rating like "4.3 /5" or float
    const rawRating = r.aggregate_rating ?? r.rating ?? r.rate ?? null;
    let rating = null;
    if (typeof rawRating === 'number') {
      rating = rawRating;
    } else if (typeof rawRating === 'string') {
      const parsed = parseFloat(rawRating.split('/')[0].trim());
      if (!isNaN(parsed)) rating = parsed;
    }

    // Parse cost string "1,000" or integer
    const rawPrice = r.price_range ?? r['approx_cost(for two people)'] ?? null;
    let price = null;
    if (typeof rawPrice === 'number') {
      price = rawPrice;
    } else if (typeof rawPrice === 'string') {
      const parsed = parseInt(rawPrice.replace(/,/g, ''), 10);
      if (!isNaN(parsed)) price = parsed;
    }

    return {
      name,
      subtitle: [cuisine, [location, city].filter(Boolean).join(", ")]
        .filter(Boolean)
        .join(" • "),
      rating,
      price,
    };
  });
}

