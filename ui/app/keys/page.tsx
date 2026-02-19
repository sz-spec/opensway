"use client";
import { useState, useEffect } from "react";
import { Key, Eye, EyeOff, Save } from "lucide-react";

export default function KeysPage() {
  const [key, setKey] = useState("");
  const [saved, setSaved] = useState(false);
  const [show, setShow] = useState(false);

  useEffect(() => {
    setKey(localStorage.getItem("opensway_api_key") || "");
  }, []);

  function save() {
    localStorage.setItem("opensway_api_key", key.trim());
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  const inputCls = "flex-1 bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 font-mono focus:outline-none focus:ring-1 focus:ring-indigo-500";

  return (
    <div className="space-y-6 max-w-xl">
      <div>
        <h1 className="text-2xl font-bold">API Keys</h1>
        <p className="text-zinc-400 text-sm mt-1">Configure your OpenSway API key for browser sessions</p>
      </div>

      <div className="card space-y-5">
        <div className="flex items-center gap-2 text-sm text-zinc-300">
          <Key size={16} className="text-indigo-400" />
          <span>API Key</span>
        </div>

        <div className="flex gap-2">
          <input
            className={inputCls}
            type={show ? "text" : "password"}
            placeholder="key_…"
            value={key}
            onChange={(e) => setKey(e.target.value)}
          />
          <button onClick={() => setShow(!show)}
            className="p-2 rounded-lg border border-zinc-700 text-zinc-400 hover:text-zinc-100 transition-colors">
            {show ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
        </div>

        <button onClick={save}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-sm font-medium transition-colors">
          <Save size={14} />
          {saved ? "Saved!" : "Save Key"}
        </button>

        <div className="border-t border-zinc-800 pt-4 space-y-2 text-sm text-zinc-400">
          <p className="font-medium text-zinc-300">Stored locally only</p>
          <p>Your key is saved in this browser&apos;s localStorage and never sent to any third party.</p>
          <p>To generate a new key, use the admin endpoint:</p>
          <pre className="bg-zinc-900 rounded p-2 text-xs text-zinc-300 overflow-x-auto">
{`POST /v1/admin/keys
{ "name": "my-app", "credit_balance": 10000 }`}
          </pre>
        </div>
      </div>
    </div>
  );
}
