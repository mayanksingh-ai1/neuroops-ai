// Illustrative fixtures only. These are not verified company results.
export const categories = [
  { name: "Late delivery", count: 284, color: "#818cf8" },
  { name: "Damaged item", count: 198, color: "#a78bfa" },
  { name: "Refund delay", count: 156, color: "#38bdf8" },
  { name: "Order cancellation", count: 121, color: "#2dd4bf" },
  { name: "Product quality", count: 94, color: "#fbbf24" },
];

export const trend = [
  { day: "Mon", complaints: 118 },
  { day: "Tue", complaints: 145 },
  { day: "Wed", complaints: 127 },
  { day: "Thu", complaints: 182 },
  { day: "Fri", complaints: 153 },
  { day: "Sat", complaints: 97 },
  { day: "Sun", complaints: 121 },
];

export const complaints = [
  {
    id: "CMP-2841",
    title: "Package marked delivered but not received",
    category: "Late delivery",
    channel: "Email",
    time: "12 min ago",
    priority: "High",
    tone: "red",
  },
  {
    id: "CMP-2838",
    title: "Received item with damaged packaging",
    category: "Damaged item",
    channel: "Web form",
    time: "38 min ago",
    priority: "Medium",
    tone: "amber",
  },
  {
    id: "CMP-2835",
    title: "Refund still pending after return",
    category: "Refund delay",
    channel: "Chat",
    time: "1 hr ago",
    priority: "High",
    tone: "red",
  },
  {
    id: "CMP-2832",
    title: "Order cancelled without notification",
    category: "Order cancellation",
    channel: "Email",
    time: "2 hrs ago",
    priority: "Low",
    tone: "slate",
  },
  {
    id: "CMP-2829",
    title: "Product quality differs from description",
    category: "Product quality",
    channel: "Web form",
    time: "3 hrs ago",
    priority: "Medium",
    tone: "amber",
  },
];
