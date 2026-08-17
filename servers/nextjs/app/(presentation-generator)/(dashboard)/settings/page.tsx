import React from 'react'
import { DISPLAY_PRODUCT } from '@/lib/product-metadata'
import UserPreferencesPage from '@/features/preferences/UserPreferencesPage'

export const metadata = {
  title: `Settings | ${DISPLAY_PRODUCT.shortName}`,
  description: 'Settings page',
}
const page = () => <UserPreferencesPage />

export default page
