export const AUTHOR_KEY_ID = "TZAR-AUTHOR-KEY-001";
export const AUTHOR_KEY_ALGORITHM = "ECDSA-P256-SHA256";
export const BACKUP_ITERATIONS = 600000;

const encoder = new TextEncoder();
const SIGN_DOMAIN = "TZAR-AUTHOR-SIGNATURE/1";
const REGISTRATION_DOMAIN = "TZAR-KEY-REGISTRATION/1";
const BACKUP_DOMAIN = encoder.encode("TZAR-AUTHOR-KEY-BACKUP/1");

export function bytesToBase64Url(value) {
  const bytes = value instanceof Uint8Array ? value : new Uint8Array(value);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

export function base64UrlToBytes(value) {
  const padded = String(value).replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(value.length / 4) * 4, "=");
  const binary = atob(padded);
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

function stableString(value) {
  if (Array.isArray(value)) return `[${value.map(stableString).join(",")}]`;
  if (value && typeof value === "object") return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableString(value[key])}`).join(",")}}`;
  return JSON.stringify(value);
}

async function digest(value) {
  return new Uint8Array(await globalThis.crypto.subtle.digest("SHA-256", encoder.encode(value)));
}

export async function publicKeyFingerprint(publicKeyJwk) {
  const canonical = stableString({ crv: publicKeyJwk.crv, kty: publicKeyJwk.kty, x: publicKeyJwk.x, y: publicKeyJwk.y });
  return `sha256:${bytesToBase64Url(await digest(canonical))}`;
}

async function deriveBackupKey(passphrase, salt, iterations) {
  const material = await globalThis.crypto.subtle.importKey("raw", encoder.encode(passphrase), "PBKDF2", false, ["deriveKey"]);
  return globalThis.crypto.subtle.deriveKey(
    { name: "PBKDF2", hash: "SHA-256", salt, iterations },
    material,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"],
  );
}

export async function encryptPrivateKey(pkcs8, passphrase, iterations = BACKUP_ITERATIONS) {
  if (typeof passphrase !== "string" || passphrase.length < 12) throw new Error("Кодовая фраза должна содержать не менее 12 символов");
  const salt = globalThis.crypto.getRandomValues(new Uint8Array(16));
  const iv = globalThis.crypto.getRandomValues(new Uint8Array(12));
  const key = await deriveBackupKey(passphrase, salt, iterations);
  const encrypted = await globalThis.crypto.subtle.encrypt({ name: "AES-GCM", iv, additionalData: BACKUP_DOMAIN }, key, pkcs8);
  return {
    cipher: "AES-256-GCM",
    kdf: "PBKDF2-SHA256",
    iterations,
    salt: bytesToBase64Url(salt),
    iv: bytesToBase64Url(iv),
    encryptedPkcs8: bytesToBase64Url(encrypted),
  };
}

async function decryptPrivateKey(backup, passphrase) {
  const salt = base64UrlToBytes(backup.encryption.salt);
  const iv = base64UrlToBytes(backup.encryption.iv);
  const encrypted = base64UrlToBytes(backup.encryption.encryptedPkcs8);
  const key = await deriveBackupKey(passphrase, salt, backup.encryption.iterations);
  try {
    return await globalThis.crypto.subtle.decrypt({ name: "AES-GCM", iv, additionalData: BACKUP_DOMAIN }, key, encrypted);
  } catch {
    throw new Error("Кодовая фраза неверна или резервная копия повреждена");
  }
}

function registrationPayload(registration) {
  const copy = structuredClone(registration);
  delete copy.proofOfPossession;
  return `${REGISTRATION_DOMAIN}\n${stableString(copy)}`;
}

function signaturePayload(seal, metadata) {
  return `${SIGN_DOMAIN}\n${stableString({ seal, schema: metadata.schema, keyId: metadata.keyId, fingerprint: metadata.fingerprint, author: metadata.author, signedAt: metadata.signedAt })}`;
}

export async function generateAuthorKey(passphrase, options = {}) {
  const author = options.author || "Александр Лацинник";
  const iterations = options.iterations || BACKUP_ITERATIONS;
  const generated = await globalThis.crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, true, ["sign", "verify"]);
  const publicKeyJwk = await globalThis.crypto.subtle.exportKey("jwk", generated.publicKey);
  const pkcs8 = await globalThis.crypto.subtle.exportKey("pkcs8", generated.privateKey);
  const fingerprint = await publicKeyFingerprint(publicKeyJwk);
  const createdAt = new Date().toISOString();
  const privateKey = await globalThis.crypto.subtle.importKey("pkcs8", pkcs8, { name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]);
  const registration = {
    schema: "tzar-author-key-registration/1.0.0",
    keyId: AUTHOR_KEY_ID,
    author,
    algorithm: AUTHOR_KEY_ALGORITHM,
    fingerprint,
    createdAt,
    status: "proposed",
    publicKeyJwk,
  };
  registration.proofOfPossession = bytesToBase64Url(await globalThis.crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, privateKey, encoder.encode(registrationPayload(registration))));
  const backup = {
    schema: "tzar-author-key-backup/1.0.0",
    keyId: AUTHOR_KEY_ID,
    author,
    algorithm: AUTHOR_KEY_ALGORITHM,
    fingerprint,
    createdAt,
    publicKeyJwk,
    encryption: await encryptPrivateKey(pkcs8, passphrase, iterations),
  };
  return { privateKey, publicKey: generated.publicKey, registration, backup };
}

export async function restoreAuthorKey(backup, passphrase) {
  if (backup?.schema !== "tzar-author-key-backup/1.0.0") throw new Error("Неизвестный формат резервной копии");
  const fingerprint = await publicKeyFingerprint(backup.publicKeyJwk);
  if (fingerprint !== backup.fingerprint) throw new Error("Открытый ключ резервной копии не соответствует отпечатку");
  const pkcs8 = await decryptPrivateKey(backup, passphrase);
  const privateKey = await globalThis.crypto.subtle.importKey("pkcs8", pkcs8, { name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]);
  const publicKey = await globalThis.crypto.subtle.importKey("jwk", backup.publicKeyJwk, { name: "ECDSA", namedCurve: "P-256" }, true, ["verify"]);
  const registration = {
    schema: "tzar-author-key-registration/1.0.0",
    keyId: backup.keyId,
    author: backup.author,
    algorithm: backup.algorithm,
    fingerprint: backup.fingerprint,
    createdAt: backup.createdAt,
    status: "proposed",
    publicKeyJwk: backup.publicKeyJwk,
  };
  registration.proofOfPossession = bytesToBase64Url(await globalThis.crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, privateKey, encoder.encode(registrationPayload(registration))));
  return { privateKey, publicKey, registration };
}

export async function verifyKeyRegistration(registration) {
  if (registration?.schema !== "tzar-author-key-registration/1.0.0") return false;
  const fingerprint = await publicKeyFingerprint(registration.publicKeyJwk);
  if (fingerprint !== registration.fingerprint) return false;
  const publicKey = await globalThis.crypto.subtle.importKey("jwk", registration.publicKeyJwk, { name: "ECDSA", namedCurve: "P-256" }, true, ["verify"]);
  return globalThis.crypto.subtle.verify({ name: "ECDSA", hash: "SHA-256" }, publicKey, base64UrlToBytes(registration.proofOfPossession), encoder.encode(registrationPayload(registration)));
}

export async function attachAuthorSignature(report, privateKey, registration) {
  if (!report?.seal) throw new Error("Паспорт не содержит контрольную печать");
  const metadata = {
    schema: "tzar-author-signature/1.0.0",
    keyId: registration.keyId,
    fingerprint: registration.fingerprint,
    author: registration.author,
    algorithm: AUTHOR_KEY_ALGORITHM,
    signedAt: new Date().toISOString(),
    publicKeyJwk: registration.publicKeyJwk,
  };
  const value = bytesToBase64Url(await globalThis.crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, privateKey, encoder.encode(signaturePayload(report.seal, metadata))));
  return { ...structuredClone(report), authorSignature: { ...metadata, value } };
}

export async function verifyAuthorSignature(report) {
  const signature = report?.authorSignature;
  if (!signature?.value || !signature?.publicKeyJwk || !report?.seal) return { valid: false, reason: "Авторская подпись отсутствует" };
  const fingerprint = await publicKeyFingerprint(signature.publicKeyJwk);
  if (fingerprint !== signature.fingerprint) return { valid: false, reason: "Отпечаток открытого ключа не совпадает" };
  const publicKey = await globalThis.crypto.subtle.importKey("jwk", signature.publicKeyJwk, { name: "ECDSA", namedCurve: "P-256" }, true, ["verify"]);
  const valid = await globalThis.crypto.subtle.verify({ name: "ECDSA", hash: "SHA-256" }, publicKey, base64UrlToBytes(signature.value), encoder.encode(signaturePayload(report.seal, signature)));
  return { valid, reason: valid ? "Авторская подпись криптографически верна" : "Авторская подпись не совпадает", fingerprint, keyId: signature.keyId, author: signature.author };
}
