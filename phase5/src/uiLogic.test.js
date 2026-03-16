import { buildRequestPayload, validateFields, mapRestaurantsToCards } from "./uiLogic.js";

describe("buildRequestPayload", () => {
  it("builds payload with trimmed strings and numeric fields", () => {
    const payload = buildRequestPayload({
      freeText: "  cheap North Indian in Delhi  ",
      city: "  Delhi ",
      location: " CP ",
      cuisine: " North Indian ",
      minRating: "4.0",
      maxPrice: "2",
      limit: "5",
    });

    expect(payload).toEqual({
      query: "cheap North Indian in Delhi",
      preferences: {
        city: "Delhi",
        location: "CP",
        cuisine: "North Indian",
        min_rating: 4.0,
        max_price_range: 2,
        limit: 5,
      },
    });
  });

  it("handles empty fields and uses defaults", () => {
    const payload = buildRequestPayload({});

    expect(payload).toEqual({
      query: null,
      preferences: {
        city: null,
        location: null,
        cuisine: null,
        min_rating: null,
        max_price_range: null,
        limit: 10,
      },
    });
  });
});

describe("validateFields", () => {
  it("rejects when no meaningful input is provided", () => {
    const result = validateFields({
      freeText: "   ",
      city: "   ",
      cuisine: " ",
    });
    expect(result.valid).toBe(false);
    expect(result.message).toContain("describe what you’re looking for");
  });

  it("accepts when free text is provided", () => {
    const result = validateFields({
      freeText: "Cheap pizza",
      city: "",
      cuisine: "",
    });
    expect(result.valid).toBe(true);
  });

  it("accepts when city or cuisine is provided", () => {
    expect(
      validateFields({
        freeText: "",
        city: "Delhi",
        cuisine: "",
      }).valid,
    ).toBe(true);

    expect(
      validateFields({
        freeText: "",
        city: "",
        cuisine: "North Indian",
      }).valid,
    ).toBe(true);
  });
});

describe("mapRestaurantsToCards", () => {
  it("maps raw restaurant objects to display cards", () => {
    const cards = mapRestaurantsToCards([
      {
        name: "Spicy House",
        city: "Delhi",
        location: "CP",
        cuisine: "North Indian",
        aggregate_rating: 4.3,
        price_range: 2,
      },
      {
        name: "Pizza Town",
        city: "Mumbai",
        locality: "Bandra",
        cuisines: "Italian",
        rating: 4.1,
      },
    ]);

    expect(cards).toHaveLength(2);
    expect(cards[0]).toEqual({
      name: "Spicy House",
      subtitle: "North Indian • CP, Delhi",
      rating: 4.3,
      price: 2,
    });
    expect(cards[1]).toEqual({
      name: "Pizza Town",
      subtitle: "Italian • Bandra, Mumbai",
      rating: 4.1,
      price: null,
    });
  });
});

