import React from 'react'
import SettingPage from './SettingPage'
import UserAccountSettings from './UserAccountSettings'
import { getServerAuthStatus } from '@/utils/serverAuth'
import { getSettingsView } from '@/utils/settingsAccess'
import { DISPLAY_PRODUCT } from '@/lib/product-metadata'

export const metadata = {
  title: `Settings | ${DISPLAY_PRODUCT.shortName}`,
  description: 'Settings page',
}
const page = async () => {
  const status = await getServerAuthStatus()

  return getSettingsView(status.role) === 'admin'
    ? <SettingPage />
    : <UserAccountSettings username={status.username ?? 'User'} />
}

export default page
