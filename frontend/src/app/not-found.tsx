import Link from "next/link";

// Root not-found (outside the [locale] segment): a minimal document, since no layout wraps it.
export default function RootNotFound() {
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", padding: "3rem", textAlign: "center" }}>
        <h1>Page not found</h1>
        <p>
          <Link href="/en">Go to ADVAR</Link>
        </p>
      </body>
    </html>
  );
}
