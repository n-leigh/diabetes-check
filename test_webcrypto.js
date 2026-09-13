// test_webcrypto.js
const { subtle } = globalThis.crypto;

function bytesToBase64Url(bytes) {
  let binary = '';
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function base64UrlToBytes(str) {
  let base64 = str.replace(/-/g, '+').replace(/_/g, '/');
  while (base64.length % 4) {
    base64 += '=';
  }
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

async function encryptV1(plaintext, passphrase) {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const enc = new TextEncoder();

  const baseKey = await subtle.importKey(
    'raw',
    enc.encode(passphrase),
    'PBKDF2',
    false,
    ['deriveKey']
  );

  const aesKey = await subtle.deriveKey(
    {
      name: 'PBKDF2',
      salt: salt,
      iterations: 310000,
      hash: 'SHA-256'
    },
    baseKey,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt']
  );

  const ciphertextBuffer = await subtle.encrypt(
    { name: 'AES-GCM', iv: iv, tagLength: 128 },
    aesKey,
    enc.encode(plaintext)
  );

  return (
    'v1.' +
    bytesToBase64Url(salt) +
    '.' +
    bytesToBase64Url(iv) +
    '.' +
    bytesToBase64Url(new Uint8Array(ciphertextBuffer))
  );
}

async function decryptV1(saltBytes, ivBytes, ciphertextBytes, passphrase) {
  const enc = new TextEncoder();
  const baseKey = await subtle.importKey(
    'raw',
    enc.encode(passphrase),
    'PBKDF2',
    false,
    ['deriveKey']
  );

  const aesKey = await subtle.deriveKey(
    {
      name: 'PBKDF2',
      salt: saltBytes,
      iterations: 310000,
      hash: 'SHA-256'
    },
    baseKey,
    { name: 'AES-GCM', length: 256 },
    false,
    ['decrypt']
  );

  const decryptedBuffer = await subtle.decrypt(
    { name: 'AES-GCM', iv: ivBytes, tagLength: 128 },
    aesKey,
    ciphertextBytes
  );

  return new TextDecoder('utf-8').decode(new Uint8Array(decryptedBuffer));
}

async function runTests() {
  const testPayload = JSON.stringify({
    v: 1,
    created_at: new Date().toISOString(),
    patient_summary: "Test patient",
    rule_results: {
      cardiovascular: { percentage: 45, label: "Moderate" },
      neuropathy_mobility: { percentage: 20, label: "Low" },
      general_burden: { percentage: 70, label: "High" },
      retinopathy: { percentage: 15, label: "Low" }
    },
    model_confidences: {
      cardiovascular: 42.1,
      neuropathy_mobility: 18.5,
      general_burden: 68.2,
      retinopathy: 14.0
    },
    recommendations: {
      overall_tier: "Moderate",
      steps: ["Routine follow-up"]
    }
  });

  const passphrase = "ClinicalTestPassphrase!2026";
  console.log("1. Encrypting test payload with 310,000 PBKDF2 iterations...");
  const t0 = Date.now();
  const encrypted = await encryptV1(testPayload, passphrase);
  const encryptTime = Date.now() - t0;
  console.log(`   Encrypted in ${encryptTime} ms. Output length: ${encrypted.length}`);

  // Decrypt with correct passphrase
  console.log("2. Decrypting with correct passphrase...");
  const parts = encrypted.split('.');
  const salt = base64UrlToBytes(parts[1]);
  const iv = base64UrlToBytes(parts[2]);
  const ciphertext = base64UrlToBytes(parts[3]);

  const decrypted = await decryptV1(salt, iv, ciphertext, passphrase);
  if (decrypted !== testPayload) {
    throw new Error("Decrypted text does not match original!");
  }
  console.log("   Decryption succeeded and verified exact payload match.");

  // Decrypt with wrong passphrase
  console.log("3. Testing wrong passphrase rejection...");
  let wrongFailed = false;
  try {
    await decryptV1(salt, iv, ciphertext, "WrongPassword");
  } catch (e) {
    wrongFailed = true;
    console.log(`   Correctly rejected wrong passphrase: ${e.name} (${e.message})`);
  }
  if (!wrongFailed) {
    throw new Error("Decryption with wrong passphrase unexpectedly succeeded!");
  }

  // Decrypt with tampered ciphertext
  console.log("4. Testing tampered ciphertext rejection...");
  let tamperFailed = false;
  const tamperedCiphertext = new Uint8Array(ciphertext);
  tamperedCiphertext[0] ^= 0xff; // Flip bits
  try {
    await decryptV1(salt, iv, tamperedCiphertext, passphrase);
  } catch (e) {
    tamperFailed = true;
    console.log(`   Correctly rejected tampered ciphertext: ${e.name} (${e.message})`);
  }
  if (!tamperFailed) {
    throw new Error("Decryption with tampered ciphertext unexpectedly succeeded!");
  }

  // Decrypt with tampered IV
  console.log("5. Testing tampered IV rejection...");
  let ivFailed = false;
  const tamperedIv = new Uint8Array(iv);
  tamperedIv[0] ^= 0xff;
  try {
    await decryptV1(salt, tamperedIv, ciphertext, passphrase);
  } catch (e) {
    ivFailed = true;
    console.log(`   Correctly rejected tampered IV: ${e.name} (${e.message})`);
  }
  if (!ivFailed) {
    throw new Error("Decryption with tampered IV unexpectedly succeeded!");
  }

  console.log("\n[WEBCRYPTO CLIENT-SIDE AES-256-GCM VERIFICATION PASSED!]");
}

runTests().catch(err => {
  console.error("WebCrypto test failed:", err);
  process.exit(1);
});

