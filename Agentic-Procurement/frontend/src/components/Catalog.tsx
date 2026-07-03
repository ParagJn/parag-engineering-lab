import React, { useEffect, useState } from "react";
import { api, type Product } from "../services/api";
import { Package, Search, AlertTriangle, Zap } from "lucide-react";

interface CatalogProps {
  onTriggerReplenishment: (wf: any) => void;
}

export const Catalog: React.FC<CatalogProps> = ({ onTriggerReplenishment }) => {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("All");
  const [replenishing, setReplenishing] = useState(false);

  useEffect(() => {
    const fetchCatalog = async () => {
      try {
        const data = await api.getProducts();
        setProducts(data);
      } catch (err: any) {
        setError(err.message || "Failed to load product catalog.");
      } finally {
        setLoading(false);
      }
    };
    fetchCatalog();
  }, []);

  const categories = ["All", ...Array.from(new Set(products.map((p) => p.category)))];

  const lowStockProducts = products.filter(p => p.inventory < 200);

  const handleTriggerReplenishment = async () => {
    if (lowStockProducts.length === 0) return;
    setReplenishing(true);
    try {
      const skus = lowStockProducts.map(p => p.sku);
      const activeWf = await api.startReplenishmentWorkflow(skus);
      onTriggerReplenishment(activeWf);
    } catch (err: any) {
      setError(err.message || "Failed to trigger auto-replenishment.");
    } finally {
      setReplenishing(false);
    }
  };

  const filteredProducts = products.filter((p) => {
    const matchesSearch = 
      p.name.toLowerCase().includes(searchTerm.toLowerCase()) || 
      p.sku.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.description.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory = selectedCategory === "All" || p.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  if (loading) {
    return (
      <div className="flex justify-center items-center py-20">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h2 className="text-2xl font-bold leading-7 text-slate-900 sm:text-3xl">CPG Product Catalog</h2>
        <p className="mt-1 text-sm text-slate-500">
          Available inventory and standard contract pricing for FreshFizz Consumer Products (Supplier).
        </p>
      </div>

      {lowStockProducts.length > 0 && (
        <div className="mb-8 bg-gradient-to-r from-red-50 to-amber-50 border-2 border-red-100 rounded-2xl p-5 shadow-sm flex flex-col md:flex-row justify-between items-start md:items-center space-y-4 md:space-y-0 relative overflow-hidden">
          <div className="absolute top-0 left-0 h-full w-1.5 bg-gradient-to-b from-[#EA4335] to-[#FBBC05]" />
          <div className="flex items-start space-x-4 pl-2">
            <div className="p-3 bg-red-100 rounded-xl text-red-600 shrink-0">
              <AlertTriangle className="h-6 w-6 animate-pulse" />
            </div>
            <div>
              <h4 className="font-bold text-slate-900 text-sm md:text-base">
                Stock Shortage Alert: {lowStockProducts.length} Items Below Threshold
              </h4>
              <p className="text-xs md:text-sm text-slate-600 mt-1">
                SKUs: {lowStockProducts.map(p => p.sku).join(", ")} are currently running below safety stock levels (200 units).
              </p>
            </div>
          </div>
          <button
            onClick={handleTriggerReplenishment}
            disabled={replenishing}
            className="w-full md:w-auto inline-flex items-center justify-center space-x-2 py-2.5 px-5 bg-gradient-to-r from-[#EA4335] to-[#FBBC05] hover:from-[#d63022] hover:to-[#e5ab04] text-white font-bold text-xs md:text-sm rounded-xl shadow-md transition-all active:scale-[0.98] cursor-pointer disabled:opacity-50"
          >
            <Zap className="h-4.5 w-4.5 fill-white" />
            <span>{replenishing ? "Starting Workflow..." : "Trigger Auto-Replenishment Run"}</span>
          </button>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border-l-4 border-red-400 p-4 mb-6 rounded-r-lg">
          <div className="text-sm text-red-700">{error}</div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4 justify-between items-center mb-6">
        {/* Search */}
        <div className="relative w-full sm:w-80">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Search className="h-5 w-5 text-slate-400" />
          </div>
          <input
            type="text"
            placeholder="Search SKU, name, or details..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="block w-full pl-10 pr-3 py-2 border border-slate-300 rounded-lg text-sm bg-white placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        {/* Categories */}
        <div className="flex space-x-1 overflow-x-auto w-full sm:w-auto pb-1 sm:pb-0">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors ${
                selectedCategory === cat
                  ? "bg-blue-600 text-white"
                  : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Catalog Table */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
        <table className="min-w-full divide-y divide-slate-200">
          <thead className="bg-slate-50">
            <tr>
              <th scope="col" className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">SKU / Product</th>
              <th scope="col" className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Category</th>
              <th scope="col" className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Pricing</th>
              <th scope="col" className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">MOQ</th>
              <th scope="col" className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Inventory Status</th>
              <th scope="col" className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Lead Time</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-slate-200">
            {filteredProducts.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-12 text-center text-slate-500">
                  No products matched your search or category filter.
                </td>
              </tr>
            ) : (
              filteredProducts.map((p) => {
                const outOfStock = p.inventory === 0;
                const lowStock = p.inventory > 0 && p.inventory < 200;
                return (
                  <tr key={p.sku} className="hover:bg-slate-50 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex items-start space-x-3">
                        <div className="p-2 bg-slate-100 rounded-lg text-slate-500 mt-0.5">
                          <Package className="h-5 w-5" />
                        </div>
                        <div>
                          <span className="text-xs font-bold text-slate-400 block">{p.sku}</span>
                          <span className="font-bold text-slate-900 block">{p.name}</span>
                          <span className="text-xs text-slate-500 line-clamp-1 mt-0.5">{p.description}</span>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-600">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-800">
                        {p.category}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-semibold text-slate-900">
                      ${p.price.toFixed(2)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-600">
                      {p.moq} units
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <div className="flex flex-col">
                        <span className="inline-flex items-center space-x-1.5 font-bold">
                          <span className={`h-2.5 w-2.5 rounded-full ${outOfStock ? "bg-red-500 animate-ping" : lowStock ? "bg-amber-500 animate-pulse" : "bg-green-500"}`} />
                          <span className={outOfStock ? "text-red-600" : lowStock ? "text-amber-600" : "text-green-600"}>
                            {p.inventory.toLocaleString()} units
                          </span>
                        </span>
                        <span className={`text-xs block mt-0.5 ml-4 ${outOfStock ? "text-red-500 font-semibold" : lowStock ? "text-amber-500 font-semibold" : "text-slate-400"}`}>
                          {outOfStock ? "Out of Stock" : lowStock ? "Low Stock Alert" : "In Stock"}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-600">
                      {p.lead_time} days
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
export default Catalog;
