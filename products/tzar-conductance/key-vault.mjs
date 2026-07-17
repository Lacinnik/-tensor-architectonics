const DATABASE = "tzar-author-key-vault";
const STORE = "keys";
const RECORD = "active";

function database() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function transact(mode, action) {
  const db = await database();
  try {
    return await new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE, mode);
      const request = action(transaction.objectStore(STORE));
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  } finally {
    db.close();
  }
}

export function storeAuthorKey(record) {
  return transact("readwrite", (store) => store.put(record, RECORD));
}

export function loadAuthorKey() {
  return transact("readonly", (store) => store.get(RECORD));
}

export function removeAuthorKey() {
  return transact("readwrite", (store) => store.delete(RECORD));
}
