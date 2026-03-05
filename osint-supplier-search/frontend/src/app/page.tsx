import Link from "next/link";
import { Search, Globe, Zap, Shield } from "lucide-react";

export default function HomePage() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-4">
      <div className="max-w-2xl w-full text-center space-y-8">
        <h1 className="text-4xl font-bold tracking-tight">
          OSINT Supplier Search
        </h1>
        <p className="text-lg text-gray-600">
          Введи название товара — система найдёт всех поставщиков
          по 20+ открытым источникам за минуту.
        </p>

        <div className="grid grid-cols-3 gap-4 text-sm text-gray-500">
          <div className="flex flex-col items-center gap-2">
            <Globe className="w-6 h-6 text-blue-600" />
            <span>20+ источников</span>
          </div>
          <div className="flex flex-col items-center gap-2">
            <Zap className="w-6 h-6 text-blue-600" />
            <span>Параллельный поиск</span>
          </div>
          <div className="flex flex-col items-center gap-2">
            <Shield className="w-6 h-6 text-blue-600" />
            <span>Проверка санкций</span>
          </div>
        </div>

        <Link
          href="/search"
          className="inline-flex items-center gap-2 bg-blue-600 text-white px-8 py-3 rounded-lg font-semibold hover:bg-blue-700 transition-colors"
        >
          <Search className="w-5 h-5" />
          Начать поиск
        </Link>
      </div>
    </main>
  );
}
