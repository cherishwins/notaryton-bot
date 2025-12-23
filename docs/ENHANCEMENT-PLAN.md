# MemeSeal Frontend Enhancement Plan

> **Goal:** Award-winning progressive enhancement with HTML → React → Three.js layers

---

## Current State vs Target State

| Metric | Current | Target |
|--------|---------|--------|
| First Paint | ~2-3s | <500ms |
| Time to Interactive | ~4-5s | <1.5s |
| Lighthouse Performance | ~50-60 | 95+ |
| Accessibility Score | 0-20 | 100 |
| Bundle Size | Unmeasured | <200KB initial |

---

## Phase 1: Security & Critical Fixes (Priority: URGENT)

### 1.1 Remove Exposed API Key
**File:** `blockburnnn/lib/api.ts:3`
```typescript
// BEFORE (DANGEROUS)
const API_NINJAS_KEY = process.env.NEXT_PUBLIC_API_NINJAS_KEY || "mHBzbxJnIQV9owM9qgj5Wg==TCvlEv90tJ4CadWw"

// AFTER
// Move to server-side API route, never expose to client
```

### 1.2 Fix TypeScript Config
**File:** `blockburnnn/next.config.mjs`
```javascript
// Remove this line
typescript: { ignoreBuildErrors: true }
```

### 1.3 Add Performance Memoization
Add to all expensive components:
- `live-ticker.tsx` - wrap token list in React.memo
- `trading-chart.tsx` - useMemo for chart data calculations
- `crypto-market-grid.tsx` - virtualize long lists

---

## Phase 2: Progressive Enhancement Architecture

### 2.1 Server Components (blockburnnn)

Convert static content to RSC:
```
app/
├── page.tsx (Server Component - static shell)
│   ├── <HeroBanner /> (Server - static)
│   ├── <Suspense fallback={<TickerSkeleton />}>
│   │   └── <LiveTicker /> (Client - dynamic)
│   └── <Suspense fallback={<ChartSkeleton />}>
│       └── <TradingChart /> (Client - dynamic)
```

### 2.2 Skeleton Loaders

Replace generic spinners with content-aware skeletons:
```tsx
// components/skeletons/TokenCardSkeleton.tsx
export function TokenCardSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="h-10 w-10 bg-gray-800 rounded-full" />
      <div className="h-4 w-24 bg-gray-800 rounded mt-2" />
      <div className="h-6 w-16 bg-gray-800 rounded mt-1" />
    </div>
  )
}
```

### 2.3 State Management (Zustand)

```typescript
// stores/appStore.ts
import { create } from 'zustand'

interface AppState {
  balance: number
  potSize: number
  activeGame: string | null
  setBalance: (balance: number) => void
  setPotSize: (size: number) => void
  setActiveGame: (game: string | null) => void
}

export const useAppStore = create<AppState>((set) => ({
  balance: 0,
  potSize: 1337,
  activeGame: null,
  setBalance: (balance) => set({ balance }),
  setPotSize: (potSize) => set({ potSize }),
  setActiveGame: (activeGame) => set({ activeGame }),
}))
```

---

## Phase 3: Three.js Integration

### 3.1 GPU Capability Detection

```typescript
// utils/gpuCapabilities.ts
export function getGPUTier(): 'high' | 'medium' | 'low' | 'none' {
  const canvas = document.createElement('canvas')
  const gl = canvas.getContext('webgl2') || canvas.getContext('webgl')

  if (!gl) return 'none'

  const debugInfo = gl.getExtension('WEBGL_debug_renderer_info')
  if (!debugInfo) return 'low'

  const renderer = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL)

  // Detect high-end GPUs
  if (/RTX|RX 6|RX 7|M1|M2|M3/i.test(renderer)) return 'high'
  if (/GTX|RX 5|Intel Iris/i.test(renderer)) return 'medium'

  return 'low'
}

export function shouldUseThreeJS(): boolean {
  const tier = getGPUTier()
  const memory = navigator.deviceMemory || 4
  const cores = navigator.hardwareConcurrency || 4

  // Only enable for capable devices
  return tier !== 'none' && tier !== 'low' && memory >= 4 && cores >= 4
}
```

### 3.2 Three.js Components

#### CrashGame 3D
```typescript
// games/CrashGame3D.tsx
import { Canvas } from '@react-three/fiber'
import { Stars, Trail } from '@react-three/drei'

function Rocket({ multiplier }: { multiplier: number }) {
  return (
    <Trail width={2} length={8} color="cyan" attenuation={(t) => t * t}>
      <mesh position={[0, multiplier * 2, 0]}>
        <coneGeometry args={[0.5, 1.5, 8]} />
        <meshStandardMaterial color="gold" emissive="orange" />
      </mesh>
    </Trail>
  )
}

export function CrashGame3D({ multiplier, crashed }) {
  return (
    <Canvas camera={{ position: [0, 5, 10] }}>
      <ambientLight intensity={0.5} />
      <pointLight position={[10, 10, 10]} />
      <Stars radius={100} depth={50} count={5000} fade />
      <Rocket multiplier={multiplier} />
      {crashed && <Explosion />}
    </Canvas>
  )
}
```

#### WebGL Matrix Rain
```glsl
// shaders/matrixRain.frag
uniform float uTime;
uniform vec2 uResolution;

float random(vec2 st) {
  return fract(sin(dot(st.xy, vec2(12.9898, 78.233))) * 43758.5453123);
}

void main() {
  vec2 uv = gl_FragCoord.xy / uResolution;

  // Create vertical columns
  float col = floor(uv.x * 40.0);
  float speed = random(vec2(col, 0.0)) * 0.5 + 0.5;

  // Animate downward
  float y = fract(uv.y + uTime * speed);

  // Fade effect
  float fade = smoothstep(0.0, 0.3, y) * smoothstep(1.0, 0.7, y);

  // Matrix green with glow
  vec3 color = vec3(0.0, fade * 0.8, 0.0);

  gl_FragColor = vec4(color, fade * 0.8);
}
```

### 3.3 Progressive Loading Pattern

```tsx
// components/ThreeJSLoader.tsx
import dynamic from 'next/dynamic'
import { shouldUseThreeJS } from '@/utils/gpuCapabilities'

const CrashGame3D = dynamic(() => import('./CrashGame3D'), { ssr: false })
const CrashGame2D = dynamic(() => import('./CrashGame2D'), { ssr: false })

export function CrashGame(props) {
  const [use3D, setUse3D] = useState(false)

  useEffect(() => {
    setUse3D(shouldUseThreeJS())
  }, [])

  return use3D ? <CrashGame3D {...props} /> : <CrashGame2D {...props} />
}
```

---

## Phase 4: Polish & Accessibility

### 4.1 Accessibility Checklist

- [ ] All buttons have aria-labels
- [ ] All images have alt text
- [ ] Focus visible on all interactive elements
- [ ] Keyboard navigation works throughout
- [ ] Screen reader announcements for dynamic content
- [ ] Color contrast meets WCAG AA
- [ ] Reduced motion preference respected

### 4.2 Error Boundaries

```tsx
// components/ErrorBoundary.tsx
import * as Sentry from '@sentry/react'

export const GameErrorBoundary = Sentry.withErrorBoundary(
  ({ children }) => children,
  {
    fallback: ({ error, resetError }) => (
      <div className="game-error">
        <h3>Game crashed! (ironic, we know)</h3>
        <button onClick={resetError}>Try Again</button>
      </div>
    ),
  }
)
```

### 4.3 Performance Monitoring

```typescript
// next.config.mjs
const withBundleAnalyzer = require('@next/bundle-analyzer')({
  enabled: process.env.ANALYZE === 'true',
})

module.exports = withBundleAnalyzer({
  // config
})
```

---

## Implementation Order

1. **Day 1-2:** Security fixes + TypeScript cleanup
2. **Day 3-4:** Server Components + Skeletons
3. **Day 5-6:** State management refactor
4. **Day 7-9:** Three.js integration (CrashGame first)
5. **Day 10-11:** Matrix Rain WebGL shader
6. **Day 12-13:** Accessibility pass
7. **Day 14:** Performance testing + deployment

---

## Success Metrics

- Lighthouse Performance: 95+
- Lighthouse Accessibility: 100
- First Contentful Paint: <1s
- Time to Interactive: <2s
- Bundle size: <200KB gzipped
- Three.js loads only on 60%+ devices (high-end)

---

*"The details are not the details. They make the design." - Charles Eames*
