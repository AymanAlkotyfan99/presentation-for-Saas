import React from 'react'
import DashboardPage from './components/DashboardPage'
import { getServerAuthStatus } from '@/utils/serverAuth'

const page = async () => {
  const status = await getServerAuthStatus()
  return (
    <DashboardPage username={status.username ?? undefined} />
  )
}

export default page
