#!/usr/bin/env node

/**
 * Authentication Testing Setup Script
 *
 * This script helps developers set up and test the authentication flow
 * in the Orion website after the recent fixes.
 */

const fs = require('fs');
const path = require('path');

// Colors for console output
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
  cyan: '\x1b[36m'
};

function log(message, color = colors.reset) {
  console.log(`${color}${message}${colors.reset}`);
}

function checkEnvironmentVariables() {
  log('\n🔍 Checking Environment Variables...', colors.cyan);

  const requiredVars = [
    'NEXT_PUBLIC_SUPABASE_URL',
    'NEXT_PUBLIC_SUPABASE_ANON_KEY',
    'NEXT_PUBLIC_SITE_URL'
  ];

  const envPath = path.join(process.cwd(), '.env.local');
  let envExists = false;
  let envContent = '';

  try {
    if (fs.existsSync(envPath)) {
      envContent = fs.readFileSync(envPath, 'utf8');
      envExists = true;
    }
  } catch (error) {
    log(`❌ Error reading .env.local: ${error.message}`, colors.red);
  }

  if (!envExists) {
    log('❌ .env.local file not found', colors.red);
    log('📝 Create .env.local with required variables:', colors.yellow);
    requiredVars.forEach(varName => {
      log(`   ${varName}=your_value_here`, colors.yellow);
    });
    return false;
  }

  let allVarsPresent = true;

  requiredVars.forEach(varName => {
    const hasVar = envContent.includes(varName) && !envContent.includes(`${varName}=`);
    const isEmpty = envContent.includes(`${varName}=\n`) || envContent.includes(`${varName}=$`);

    if (!envContent.includes(varName)) {
      log(`❌ Missing: ${varName}`, colors.red);
      allVarsPresent = false;
    } else if (isEmpty) {
      log(`⚠️  Empty: ${varName}`, colors.yellow);
      allVarsPresent = false;
    } else {
      log(`✅ Found: ${varName}`, colors.green);
    }
  });

  return allVarsPresent;
}

function checkSupabaseSetup() {
  log('\n🏗️  Checking Supabase Setup...', colors.cyan);

  const supabaseFiles = [
    'utils/supabase/client.ts',
    'utils/supabase/server.ts',
    'utils/supabase/middleware.ts'
  ];

  let allFilesExist = true;

  supabaseFiles.forEach(filePath => {
    const fullPath = path.join(process.cwd(), filePath);
    if (fs.existsSync(fullPath)) {
      log(`✅ ${filePath}`, colors.green);
    } else {
      log(`❌ Missing: ${filePath}`, colors.red);
      allFilesExist = false;
    }
  });

  return allFilesExist;
}

function checkAuthFiles() {
  log('\n🔐 Checking Authentication Files...', colors.cyan);

  const authFiles = [
    'app/login/page.tsx',
    'app/login/actions.tsx',
    'app/signup/page.tsx',
    'app/signup/actions.tsx',
    'app/auth/callback/route.ts',
    'hooks/use-user.tsx',
    'lib/auth-schemas.ts'
  ];

  let allFilesExist = true;

  authFiles.forEach(filePath => {
    const fullPath = path.join(process.cwd(), filePath);
    if (fs.existsSync(fullPath)) {
      log(`✅ ${filePath}`, colors.green);
    } else {
      log(`❌ Missing: ${filePath}`, colors.red);
      allFilesExist = false;
    }
  });

  return allFilesExist;
}

function checkDebugTools() {
  log('\n🐛 Checking Debug Tools...', colors.cyan);

  const debugFiles = [
    'utils/debug/auth-debug.ts',
    'app/test-auth/page.tsx'
  ];

  let allFilesExist = true;

  debugFiles.forEach(filePath => {
    const fullPath = path.join(process.cwd(), filePath);
    if (fs.existsSync(fullPath)) {
      log(`✅ ${filePath}`, colors.green);
    } else {
      log(`❌ Missing: ${filePath}`, colors.red);
      allFilesExist = false;
    }
  });

  return allFilesExist;
}

function printTestingInstructions() {
  log('\n📋 Testing Instructions', colors.bright);
  log('═══════════════════════', colors.bright);

  log('\n1. 🚀 Start Development Server:', colors.cyan);
  log('   npm run dev', colors.yellow);
  log('   # or');
  log('   bun run dev', colors.yellow);

  log('\n2. 🔍 Open Debug Dashboard:', colors.cyan);
  log('   http://localhost:3000/test-auth', colors.yellow);
  log('   (Development mode only)', colors.magenta);

  log('\n3. 🧪 Test Authentication Flow:', colors.cyan);
  log('   • Email Signup: http://localhost:3000/signup', colors.yellow);
  log('   • Email Login: http://localhost:3000/login', colors.yellow);
  log('   • Dashboard: http://localhost:3000/dashboard', colors.yellow);

  log('\n4. 🛠️  Console Debug Commands:', colors.cyan);
  log('   window.authDebug.logState()    - Check auth state', colors.yellow);
  log('   window.authDebug.testFlow()    - Test consistency', colors.yellow);
  log('   window.authDebug.monitor()     - Monitor changes', colors.yellow);
  log('   window.authDebug.clear()       - Clear auth data', colors.yellow);
  log('   window.authDebug.signOut()     - Force sign out', colors.yellow);

  log('\n5. ✅ Expected Behavior:', colors.cyan);
  log('   • No "unexpected error occurred" messages', colors.green);
  log('   • Smooth login/signup flow', colors.green);
  log('   • Dashboard loads with user data immediately', colors.green);
  log('   • Clean sign out with redirect to home', colors.green);
  log('   • Proper middleware route protection', colors.green);
}

function printTroubleshootingGuide() {
  log('\n🔧 Troubleshooting Guide', colors.bright);
  log('═════════════════════════', colors.bright);

  log('\n❌ "Unexpected error occurred" during login:', colors.red);
  log('   • Check console for NEXT_REDIRECT errors', colors.yellow);
  log('   • Verify action files are updated', colors.yellow);
  log('   • Use window.authDebug.logState() to check state', colors.yellow);

  log('\n❌ Dashboard shows "Welcome, user":', colors.red);
  log('   • Check if UserProvider wraps the app', colors.yellow);
  log('   • Verify session is properly established', colors.yellow);
  log('   • Use debug tools to inspect user context', colors.yellow);

  log('\n❌ OAuth doesn\'t complete authentication:', colors.red);
  log('   • Check callback URL configuration', colors.yellow);
  log('   • Verify NEXT_PUBLIC_SITE_URL is correct', colors.yellow);
  log('   • Check auth callback logs', colors.yellow);

  log('\n❌ Sign out doesn\'t work:', colors.red);
  log('   • Use window.authDebug.signOut()', colors.yellow);
  log('   • Clear auth data with window.authDebug.clear()', colors.yellow);
  log('   • Refresh page and try again', colors.yellow);
}

function main() {
  log('🔐 Orion Authentication Testing Setup', colors.bright);
  log('══════════════════════════════════════', colors.bright);

  const envOk = checkEnvironmentVariables();
  const supabaseOk = checkSupabaseSetup();
  const authOk = checkAuthFiles();
  const debugOk = checkDebugTools();

  const allChecksPass = envOk && supabaseOk && authOk && debugOk;

  log('\n📊 Setup Status:', colors.cyan);
  log(`Environment Variables: ${envOk ? '✅' : '❌'}`, envOk ? colors.green : colors.red);
  log(`Supabase Files: ${supabaseOk ? '✅' : '❌'}`, supabaseOk ? colors.green : colors.red);
  log(`Auth Files: ${authOk ? '✅' : '❌'}`, authOk ? colors.green : colors.red);
  log(`Debug Tools: ${debugOk ? '✅' : '❌'}`, debugOk ? colors.green : colors.red);

  if (allChecksPass) {
    log('\n🎉 All checks passed! Ready for testing.', colors.green);
    printTestingInstructions();
  } else {
    log('\n⚠️  Some issues found. Please resolve them before testing.', colors.yellow);
    printTroubleshootingGuide();
  }

  log('\n📖 For detailed guide, see: AUTH_TESTING_GUIDE.md', colors.cyan);
  log('\n🏁 Happy testing!', colors.bright);
}

// Run the script
if (require.main === module) {
  main();
}

module.exports = {
  checkEnvironmentVariables,
  checkSupabaseSetup,
  checkAuthFiles,
  checkDebugTools
};
