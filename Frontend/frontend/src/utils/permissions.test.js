import assert from 'node:assert/strict'
import test from 'node:test'
import { canManageApprovals, canUseOperationalFeatures, hasAnyRole } from './permissions.js'

test('operational features are available only to backend-authorized roles', () => {
  assert.equal(canUseOperationalFeatures({ role: 'operator' }), true)
  assert.equal(canUseOperationalFeatures({ role: 'viewer' }), false)
})

test('approval actions are restricted to managers and admins', () => {
  assert.equal(canManageApprovals({ role: 'manager' }), true)
  assert.equal(canManageApprovals({ role: 'operator' }), false)
})

test('role matching is case-insensitive and rejects missing profiles', () => {
  assert.equal(hasAnyRole({ role: 'ADMIN' }, ['admin']), true)
  assert.equal(hasAnyRole(null, ['admin']), false)
})
