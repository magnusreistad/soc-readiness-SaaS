"use client";

import { Suspense, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

function SignupForm() {
  const router = useRouter();
  const [form, setForm] = useState({
    org_name: "",
    admin_name: "",
    email: "",
    password: "",
    confirm_password: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async () => {
  setError(null);

  if (form.password !== form.confirm_password) {
    setError("Passwords do not match.");
    return;
  }
  if (form.password.length < 10) {
    setError("Password must be at least 10 characters.");
    return;
  }

  setLoading(true);
  try {
    const res = await fetch(`${window.location.origin}/api/proxy/v1/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form),
    });

    const rawText = await res.text();

    let data: any;
    try {
      data = JSON.parse(rawText);
    } catch {
      setError(`Server returned non-JSON (${res.status}): ${rawText.slice(0, 100)}`);
      return;
    }

    if (!res.ok) {
      setError(data.detail || "Signup failed.");
      return;
    }

    router.push("/login?message=Workspace+created+-+you+can+now+sign+in");
  } catch (err) {
    console.error("Signup fetch error:", err);
    setError(`Fetch failed: ${err}`);
  } finally {
    setLoading(false);
  }
};

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-2xl shadow-lg p-8">
          <div className="flex flex-col items-center mb-6">
            <div className="w-12 h-12 bg-indigo-600 rounded-xl flex items-center justify-center mb-4">
              <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
                />
              </svg>
            </div>
            <h1 className="text-2xl font-bold text-gray-900">Create your workspace</h1>
            <p className="text-sm text-gray-500 mt-1">
              Set up your SOC 2 compliance platform in under a minute.
            </p>
          </div>

          {error && (
            <div className="mb-4 rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3 text-sm">
              {error}
            </div>
          )}

          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Company name</label>
              <input name="org_name" type="text" placeholder="Acme Corp"
                value={form.org_name} onChange={handleChange}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Your full name</label>
              <input name="admin_name" type="text" placeholder="Jane Smith"
                value={form.admin_name} onChange={handleChange}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Work email</label>
              <input name="email" type="email" placeholder="jane@acmecorp.com"
                value={form.email} onChange={handleChange}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Password <span className="text-gray-400">(min 10 characters)</span>
              </label>
              <input name="password" type="password" placeholder="••••••••••"
                value={form.password} onChange={handleChange}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Confirm password</label>
              <input name="confirm_password" type="password" placeholder="••••••••••"
                value={form.confirm_password} onChange={handleChange}
                onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <button onClick={handleSubmit} disabled={loading}
              className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-medium py-2.5 rounded-lg transition-colors mt-2"
            >
              {loading ? "Creating workspace…" : "Create workspace"}
            </button>
          </div>

          <p className="text-center text-sm text-gray-500 mt-6">
            Already have a workspace?{" "}
            <Link href="/login" className="text-indigo-600 hover:underline font-medium">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}

export default function SignupPage() {
  return (
    <Suspense>
      <SignupForm />
    </Suspense>
  );
}