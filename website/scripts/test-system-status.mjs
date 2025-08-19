#!/usr/bin/env node

/**
 * Test script for the System Status API
 *
 * This script tests the /api/system-status endpoint to ensure it's working correctly.
 * Run with: node scripts/test-system-status.mjs
 */

import http from 'http';

// Configuration
const HOST = 'localhost';
const PORT = 3000;
const ENDPOINT = '/api/system-status';

console.log('🔍 Testing System Status API...\n');

// Make request to the API endpoint
const options = {
  hostname: HOST,
  port: PORT,
  path: ENDPOINT,
  method: 'GET',
  headers: {
    'Content-Type': 'application/json',
  },
};

const req = http.request(options, (res) => {
  let data = '';

  // Collect response data
  res.on('data', (chunk) => {
    data += chunk;
  });

  // Handle response end
  res.on('end', () => {
    console.log(`📡 Response Status: ${res.statusCode}`);
    console.log(`📦 Response Headers:`, res.headers);
    console.log('\n📄 Response Body:');

    try {
      const jsonData = JSON.parse(data);
      console.log(JSON.stringify(jsonData, null, 2));

      // Validate response structure
      validateResponse(jsonData);

    } catch (error) {
      console.error('❌ Failed to parse JSON response:', error.message);
      console.log('Raw response:', data);
    }
  });
});

// Handle request errors
req.on('error', (error) => {
  console.error('❌ Request failed:', error.message);

  if (error.code === 'ECONNREFUSED') {
    console.log('\n💡 Make sure your Next.js development server is running:');
    console.log('   npm run dev');
    console.log('   # or');
    console.log('   bun run dev');
  }
});

// Send the request
req.end();

/**
 * Validate the API response structure
 */
function validateResponse(data) {
  console.log('\n🔍 Validating response structure...');

  const requiredFields = ['overall', 'services', 'lastUpdated'];
  const validStatuses = ['operational', 'degraded', 'outage', 'maintenance'];

  let isValid = true;

  // Check required fields
  for (const field of requiredFields) {
    if (!(field in data)) {
      console.error(`❌ Missing required field: ${field}`);
      isValid = false;
    }
  }

  // Validate overall status
  if (data.overall && !validStatuses.includes(data.overall)) {
    console.error(`❌ Invalid overall status: ${data.overall}`);
    console.log(`   Valid statuses: ${validStatuses.join(', ')}`);
    isValid = false;
  }

  // Validate services array
  if (data.services && Array.isArray(data.services)) {
    for (let i = 0; i < data.services.length; i++) {
      const service = data.services[i];
      if (!service.name || !service.status) {
        console.error(`❌ Service ${i} missing name or status:`, service);
        isValid = false;
      } else if (!validStatuses.includes(service.status)) {
        console.error(`❌ Service "${service.name}" has invalid status: ${service.status}`);
        isValid = false;
      }
    }
  } else if (data.services !== undefined) {
    console.error(`❌ Services should be an array, got: ${typeof data.services}`);
    isValid = false;
  }

  // Validate lastUpdated
  if (data.lastUpdated) {
    const date = new Date(data.lastUpdated);
    if (isNaN(date.getTime())) {
      console.error(`❌ Invalid lastUpdated date: ${data.lastUpdated}`);
      isValid = false;
    }
  }

  // Print validation results
  if (isValid) {
    console.log('✅ Response structure is valid!');

    // Print summary
    console.log('\n📊 Status Summary:');
    console.log(`   Overall Status: ${getStatusEmoji(data.overall)} ${data.overall}`);
    console.log(`   Services Monitored: ${data.services ? data.services.length : 0}`);
    console.log(`   Last Updated: ${new Date(data.lastUpdated).toLocaleString()}`);

    if (data.services && data.services.length > 0) {
      console.log('\n🔧 Service Details:');
      data.services.forEach((service, index) => {
        console.log(`   ${index + 1}. ${service.name}: ${getStatusEmoji(service.status)} ${service.status}`);
      });
    }

    // Environment check
    console.log('\n🌍 Environment Check:');
    if (process.env.BETTERSTACK_UPTIME_STATUS_KEY) {
      console.log('   ✅ BETTERSTACK_UPTIME_STATUS_KEY is set');
    } else {
      console.log('   ⚠️  BETTERSTACK_UPTIME_STATUS_KEY not found in environment');
      console.log('      The API will return default "operational" status');
    }

  } else {
    console.log('❌ Response structure validation failed!');
    process.exit(1);
  }
}

/**
 * Get emoji for status type
 */
function getStatusEmoji(status) {
  switch (status) {
    case 'operational':
      return '✅';
    case 'degraded':
      return '⚠️';
    case 'outage':
      return '❌';
    case 'maintenance':
      return '🔧';
    default:
      return '❓';
  }
}
