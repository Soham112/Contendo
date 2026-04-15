'use client'

import { useEffect, useState } from 'react'

export default function LoadingWordmark() {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const id = requestAnimationFrame(() => setVisible(true))
    return () => cancelAnimationFrame(id)
  }, [])

  return (
    <div
      className="min-h-screen flex items-center justify-center"
      style={{ background: '#faf9f8' }}
    >
      <span
        className="font-headline italic text-[2rem] text-[#2f3333]"
        style={{
          opacity: visible ? 1 : 0,
          transition: 'opacity 300ms ease',
        }}
      >
        Contendo
      </span>
    </div>
  )
}
