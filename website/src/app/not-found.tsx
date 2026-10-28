import Link from "next/link";

// Keep the missing-page response usable without permitting inline styles or scripts.
export default function NotFound() {
  return <main><h1>Page not found</h1><Link href="/">Return to Death&apos;s Warrant</Link></main>;
}
