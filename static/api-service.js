/**
 * TrustCheck API Service
 * Centralized service file for all network communication with existing backend endpoints.
 */

const API_TIMEOUT_MS = 30000;

async function requestWithTimeout(url, options = {}, timeoutMs = API_TIMEOUT_MS) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal
    });
    clearTimeout(timeoutId);

    const contentType = response.headers.get('content-type') || '';
    let data;
    if (contentType.includes('application/json')) {
      data = await response.json();
    } else {
      const text = await response.text();
      try {
        data = JSON.parse(text);
      } catch (e) {
        data = { error: text || 'Server returned non-JSON response.' };
      }
    }

    if (!response.ok) {
      const errorMsg = data && data.error ? data.error : `Server error (${response.status})`;
      throw new Error(errorMsg);
    }

    return data;
  } catch (error) {
    clearTimeout(timeoutId);
    if (error.name === 'AbortError') {
      throw new Error('Request timed out. Please try again.');
    }
    throw error;
  }
}

export const apiService = {
  /**
   * Fast single review analysis
   * @param {string} text
   * @returns {Promise<Object>} Single review forensics
   */
  async analyzeSingle(text) {
    if (!text || !text.trim()) {
      throw new Error('Please enter review text to analyze.');
    }
    return await requestWithTimeout('/api/analyze-single', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify({ text: text.trim() })
    });
  },

  /**
   * Batch analyze pasted review lines
   * @param {string} text
   * @returns {Promise<Object>} Dashboard data
   */
  async analyzePasted(text) {
    if (!text || !text.trim()) {
      throw new Error('Please enter reviews to analyze.');
    }
    return await requestWithTimeout('/analyze', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify({
        input_mode: 'manual',
        pasted_reviews: text.trim(),
        format: 'json'
      })
    });
  },

  /**
   * Upload CSV file for batch analysis
   * @param {File} file
   * @returns {Promise<Object>} Dashboard data
   */
  async uploadCsv(file) {
    if (!file) {
      throw new Error('Please select a CSV file.');
    }
    const formData = new FormData();
    formData.append('input_mode', 'csv');
    formData.append('csv_file', file);
    formData.append('format', 'json');

    return await requestWithTimeout('/analyze', {
      method: 'POST',
      headers: {
        'Accept': 'application/json'
      },
      body: formData
    });
  },

  /**
   * Scrape and analyze reviews for an Amazon or Flipkart URL
   * @param {string} url
   * @returns {Promise<Object>} Dashboard data
   */
  async scrapeUrl(url) {
    if (!url || !url.trim()) {
      throw new Error('Please provide an Amazon or Flipkart product URL.');
    }
    return await requestWithTimeout('/analyze', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify({
        input_mode: 'url',
        product_url: url.trim(),
        format: 'json'
      })
    });
  },

  /**
   * Fetch default benchmark telemetry data
   * @returns {Promise<Object>}
   */
  async fetchDefaultIntelligence() {
    return await requestWithTimeout('/api/default-intelligence', {
      method: 'GET',
      headers: { 'Accept': 'application/json' }
    });
  }
};
