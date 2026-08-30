'use strict'

// Stub for `thread-stream`.
//
// pino requires thread-stream at the top of lib/transport.js, but it is only
// instantiated when a pino transport is configured. Nothing in this app does —
// pino only reaches the bundle transitively through @walletconnect/logger.
//
// The real package resolves its worker with `join(__dirname, 'lib', 'worker.js')`
// inside a `new Worker(...)` call. Turbopack cannot statically resolve that, so
// it falls back to a context module over the whole package directory and then
// fails on README.md, LICENSE, *.test.ts and the .zip fixtures shipped in
// test/. Aliasing the package here keeps that directory out of the graph.
//
// See next.config.mjs (turbopack.resolveAlias).

const { EventEmitter } = require('events')

class ThreadStream extends EventEmitter {
  constructor () {
    super()
    throw new Error(
      'thread-stream is stubbed out in this build; pino transports are not supported here.'
    )
  }
}

module.exports = ThreadStream
module.exports.default = ThreadStream
