import "./globals.css";
import ClientLayout from "./ClientLayout";

export const metadata = {
  title: "PharmAgent Dashboard",
  description: "Web dashboard for WhatsApp PharmAgent — manage inventory, transactions, invoices, and billing",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <ClientLayout>
          {children}
        </ClientLayout>
      </body>
    </html>
  );
}
