using System.Runtime.InteropServices;

namespace CSharpHelpers {  
  
  public static class UnsafeHelpers {
    
    /// <summary>
    /// Copies a block of memory using source pointer to a float array.
    /// </summary>
    /// <param name="sourcePtr">The pointer to a source block of memory</param>
    /// <param name="destination">The destination float array</param>
    /// <param name="length">The number of bytes to copy</param>
    public static unsafe void CopyPtrToArrayAtIndex<T>(IntPtr sourcePtr, T[] destination, int index, int length)  where T : unmanaged {
      int sizeOfT = sizeof(T);
      int nBytes = length * sizeOfT;
      // Make sure the destination array has enough space
      if (index + length > destination.Length)
        throw new ArgumentException("Destination array does not have enough space.");

      // Pin the destination array
      GCHandle gch = GCHandle.Alloc(destination, GCHandleType.Pinned);

      try {
        IntPtr destinationPtr = gch.AddrOfPinnedObject();

        // Calculate the byte offset into the array where the copy will begin
        long byteOffset = index * sizeOfT;

        // Add the byte offset to the destination address
        destinationPtr = new IntPtr(destinationPtr.ToInt64() + byteOffset);

        // Perform the memory copy
        Buffer.MemoryCopy(sourcePtr.ToPointer(), (void*)destinationPtr, nBytes, nBytes); }
      finally {
        // Always free the GCHandle!
        gch.Free(); }

    } } }
