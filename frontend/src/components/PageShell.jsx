import { motion } from 'framer-motion'
import AmbientGrid from './AmbientGrid.jsx'
import TopNav from './TopNav.jsx'

/**
 * Standard page wrapper — ambient grid background, top nav, animated entry.
 */
export default function PageShell({ children, className = '' }) {
  return (
    <>
      <AmbientGrid />
      <TopNav />
      <motion.main
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -8 }}
        transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        className={`flex-1 ${className}`}
      >
        {children}
      </motion.main>
    </>
  )
}
