export interface ArrayMinOptions {
    /**
     * Start index (inclusive) for the slice within which we look for the minimum.
     */
    fromIndex?: number;
    /**
     * End index (exclusive) for the slice within which we look for the minimum
     */
    toIndex?: number;
}
/**
 * Computes the minimum of the given values.
 */
export default function min(input: ArrayLike<number>, options?: ArrayMinOptions): number;
//# sourceMappingURL=index.d.ts.map