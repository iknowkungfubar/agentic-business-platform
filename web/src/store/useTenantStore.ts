/* Tenant branding store — resolves white-label config from custom domain.
 *
 * On initial load, reads window.location.hostname, fetches branding
 * details from the API, and dynamically injects CSS custom properties
 * into the document root.
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface TenantBranding {
  tenant_id: number;
  tenant_name: string;
  slug: string;
  logo_url: string;
  primary_color: string;
  secondary_color: string;
}

interface TenantState {
  branding: TenantBranding | null;
  loading: boolean;
  resolved: boolean;
  resolveTenant: () => Promise<void>;
  applyBranding: (branding: TenantBranding) => void;
}

export const useTenantStore = create<TenantState>()(
  persist(
    (set, get) => ({
      branding: null,
      loading: false,
      resolved: false,

      resolveTenant: async () => {
        const state = get();
        if (state.resolved) return;

        set({ loading: true });
        const hostname = window.location.hostname;

        try {
          const resp = await fetch(
            `${API_BASE}/api/v1/tenant/resolve?domain=${encodeURIComponent(hostname)}`,
          );
          if (resp.ok) {
            const branding: TenantBranding = await resp.json();
            get().applyBranding(branding);
            set({ branding, loading: false, resolved: true });
          } else {
            set({ loading: false, resolved: true });
          }
        } catch {
          set({ loading: false, resolved: true });
        }
      },

      applyBranding: (branding: TenantBranding) => {
        const root = document.documentElement;
        root.style.setProperty('--primary-color', branding.primary_color);
        root.style.setProperty('--secondary-color', branding.secondary_color);
        if (branding.logo_url) {
          root.style.setProperty('--logo-url', `url(${branding.logo_url})`);
        }
        document.title = `${branding.tenant_name} — AI Platform`;
      },
    }),
    {
      name: 'turin-tenant-storage',
      partialize: (state) => ({
        branding: state.branding,
        resolved: state.resolved,
      }),
    },
  ),
);
