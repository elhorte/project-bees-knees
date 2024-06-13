module BeesUtil.MasterCancellationToken

open System
open System.Collections.Generic
open System.Threading

/// Represents a collection of CancellationToken objects managed by a master CancellationToken.
type MasterCancellationToken() =
  let tokenSources = List<CancellationTokenSource>()

  /// Add a CancellationTokenSource to be managed.
  member this.Add(cancellationTokenSource: CancellationTokenSource) =
    tokenSources.Add (cancellationTokenSource)

  /// Add a CancellationTokenSource to be managed.
  member this.Remove(cancellationTokenSource: CancellationTokenSource) =
    tokenSources.Remove cancellationTokenSource

  /// Cancels all CancellationTokenSource objects managed by this master CancellationTokenSource.
  member this.CancelAll() =
    for cts in tokenSources do
     cts.Cancel()

  /// A sequence of the CancellationToken objects.
  member this.TokenSources = tokenSources
